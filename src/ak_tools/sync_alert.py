import json
import os
import os.path as osp
import sys
import logging
import subprocess
import re
import boto3
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
AVC_API_ENDPOINT = 'https://analytics-kpis.netradyne.info/avc_api'
s3_sync_path = 's3://netradyne-sharing/analytics/ashok/alert_debug/'
LOCAL_STORAGE_DIR = osp.expanduser('~/neokpi')

logger = logging.getLogger(__name__)


def infer_alert_type(alert_value):
    """Infer alert input type from value format.

    Rules:
    - all digits -> alert_id
    - alphanumeric with optional hyphens (contains a letter) -> avid
    """
    value = str(alert_value).strip()
    if value.isdigit():
        return 'alert_id'

    if re.fullmatch(r'[A-Za-z0-9-]+', value) and re.search(r'[A-Za-z]', value):
        return 'avid'

    logger.warning('Could not confidently infer alert type for %s, defaulting to alert_id', alert_value)
    return 'alert_id'


def parse_s3_uri(s3_uri):
    """Parse s3://bucket/prefix URI into bucket and prefix."""
    s3_uri = str(s3_uri).strip()
    if not s3_uri.startswith('s3://'):
        raise ValueError(f'Invalid S3 URI: {s3_uri}')

    no_scheme = s3_uri[len('s3://'):]
    if '/' in no_scheme:
        bucket, prefix = no_scheme.split('/', 1)
    else:
        bucket, prefix = no_scheme, ''

    bucket = bucket.strip()
    prefix = prefix.strip('/')
    if not bucket:
        raise ValueError(f'Invalid S3 URI (missing bucket): {s3_uri}')
    return bucket, prefix


def sync_folder_to_s3(local_dir, destination_s3_uri):
    """Upload all files from local_dir to destination_s3_uri recursively."""
    if not osp.isdir(local_dir):
        logger.warning('Local sync directory does not exist: %s', local_dir)
        return

    bucket, prefix = parse_s3_uri(destination_s3_uri)
    s3_client = boto3.client('s3')
    uploaded_count = 0

    for root, _, files in os.walk(local_dir):
        for filename in files:
            local_path = osp.join(root, filename)
            relative_path = osp.relpath(local_path, local_dir).replace(os.sep, '/')
            s3_key = f'{prefix}/{relative_path}' if prefix else relative_path
            logger.info('Uploading %s to s3://%s/%s', local_path, bucket, s3_key)
            s3_client.upload_file(local_path, bucket, s3_key)
            uploaded_count += 1

    logger.info('S3 sync complete: uploaded %d files to %s', uploaded_count, destination_s3_uri)


def get_compression_settings(level):
    """Return ffmpeg settings for supported compression levels."""
    levels = {
        1: {'resolution': '480', 'fps': 20, 'preset': 'veryfast', 'crf': '28'},
        2: {'resolution': '360', 'fps': 15, 'preset': 'slow', 'crf': '32'},
        3: {'resolution': '240', 'fps': 12, 'preset': 'veryslow', 'crf': '34'},
    }
    if level not in levels:
        logger.warning('Unsupported compression level %s, defaulting to 1', level)
        return levels[1]
    return levels[level]


def downscale_video(video_path, output_path, compression_level=1):
    """Downscale video using ffmpeg settings from a compression profile.
    
    Args:
        video_path (str): path to input video
        output_path (str): path to output video
        compression_level (int): profile level (1=current, 2=smaller, 3=smallest)
    """
    if not os.path.exists(video_path):
        logger.warning('Video file not found: %s', video_path)
        return False
    
    try:
        # # Check if ffmpeg is available
        # result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        # if result.returncode != 0:
        #     logger.warning('ffmpeg not available, skipping downscaling')
        #     return False
            
        settings = get_compression_settings(compression_level)
        resolution = settings['resolution']
        fps = settings['fps']
        preset = settings['preset']
        crf = settings['crf']

        cmd = [
            'ffmpeg', '-i', video_path,
            '-vf', f'scale=-2:{resolution}:flags=fast_bilinear,fps={fps}',
            '-c:v', 'libx264', '-preset', preset, '-crf', crf,
            '-c:a', 'copy',
            '-movflags', '+faststart',
            '-y', output_path
        ]
        logger.info(
            'Downscaling %s using compression level %s (%sp@%sfps, preset=%s, crf=%s)',
            video_path,
            compression_level,
            resolution,
            fps,
            preset,
            crf,
        )
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        
        if result.returncode != 0:
            logger.error('ffmpeg error: %s', result.stderr.decode('utf-8', errors='ignore'))
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            os.remove(video_path)
            os.rename(output_path, video_path)
            # logger.info('Downscaling complete: %s', video_path)
            return True
        else:
            logger.error('Output file empty or missing after downscaling: %s', output_path)
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
    except FileNotFoundError:
        logger.warning('ffmpeg not found in PATH, skipping downscaling')
        return False
    except subprocess.TimeoutExpired:
        logger.error('ffmpeg timeout while processing: %s', video_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except Exception as e:
        logger.error('Error during downscaling %s: %s', video_path, str(e))
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def should_download_key(key, prefix):
    allowed_files = {'0.mp4', '1.mp4', '8.mp4','metadata.txt'}
    filename = key.replace(prefix + '/', '').split('/')[-1]
    return filename in allowed_files


def requests_retry_session(retries=5, backoff_factor=1,
                           status_forcelist=(400, 429, 500, 502, 503, 504),
                           session=None):
    """Define the retry strategy for requests."""
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def query_api(input_data, env='production'):
    """Call the AVC API to get video metadata.

    Args:
        input_data (dict): Single key dictionary with supported keys - [alert_id, aaid, avid, avsid, request_id]
        env (str): 'production' or 'staging'

    Returns:
        response (dict): API response with video paths and metadata
    """
    env = "secondary" if env == "staging" else "primary"
    params = {
        'input_data': input_data,
        'anonymize_environment': env,
        'source': 'debug',
        'api_version': 'v2'
    }
    logger.info('Invoking the AVC API with input %s', params)
    response = requests_retry_session(retries=5).post(AVC_API_ENDPOINT, json=params)
    logger.info('Received response from AVC API: %s', response.text)
    return json.loads(response.text)


def download_data(bucket, prefix, down_dir, downscale=False, local_subdir=None, compression_level=1):
    """Download data from S3.

    Args:
        bucket (str): bucket name
        prefix (str): prefix to download
        down_dir (str): path to directory for download
        downscale (bool): whether to downscale downloaded mp4 videos
        local_subdir (str|None): optional local subfolder under down_dir
        compression_level (int): compression profile level (1, 2, or 3)
    """
    target_subdir = str(local_subdir) if local_subdir is not None else str(prefix)
    target_subdir = target_subdir.strip(osp.sep)
    target_dir = osp.join(down_dir, target_subdir) if target_subdir else down_dir

    logger.info('Syncing data from %s/%s to %s', bucket, prefix, target_dir)
    prefix = str(prefix).rstrip(osp.sep)
    if not osp.exists(target_dir):
        os.makedirs(target_dir)
    s3_resource = boto3.resource('s3')
    bucket_obj = s3_resource.Bucket(bucket)
    objects = (
        obj for obj in bucket_obj.objects.filter(Prefix=prefix + '/')
        if should_download_key(obj.key, prefix)
    )
    logger.debug('Downloading the requested data. This might take time')
    for obj in objects:
        tokens = obj.key.replace(prefix + '/', '').split('/')
        filename = tokens[-1]
        logger.info('Downloading %s', obj.key)
        if not osp.exists(target_dir):
            os.makedirs(target_dir)
        file_path = osp.join(target_dir, filename)
        bucket_obj.download_file(obj.key, file_path)
        
        # Downscale video files when explicitly requested.
        if downscale and filename.endswith('.mp4'):
            downscale_video(file_path, file_path + '.tmp.mp4', compression_level=compression_level)

def download_alert(alert_id, download_dir, env='production', input_type='alert_id', downscale=False, compression_level=1):
    """Download alert data from S3.

    Args:
        alert_id (str): alert ID, avid, aaid, etc.
        download_dir (str): path to download directory
        env (str): 'production' or 'staging'
        input_type (str): type of input - 'alert_id', 'avid', 'aaid'
        downscale (bool): whether to downscale downloaded mp4 videos
        compression_level (int): compression profile level (1, 2, or 3)

    Returns:
        list: list of downloaded video folders
    """
    input_data = {input_type: alert_id}
    result = query_api(input_data, env)
    
    if result.get('msg') != 'success':
        logger.error('API call failed for %s: %s', alert_id, result)
        return []
    
    s3_path_list = result.get('s3_bucket')
    if not isinstance(s3_path_list, list):
        s3_path_list = [s3_path_list]
    
    video_folders = []
    multiple_sources = len(s3_path_list) > 1
    for idx, s3_path in enumerate(s3_path_list):
        s3_tokens = s3_path.split('/')
        parent_s3_bucket = s3_tokens[0]
        s3_prefix = '/'.join(s3_tokens[1:])
        down_dir = osp.join(download_dir, str(alert_id))
        local_subdir = f'source_{idx + 1}' if multiple_sources else ''
        
        download_data(
            parent_s3_bucket,
            s3_prefix,
            down_dir=down_dir,
            downscale=downscale,
            local_subdir=local_subdir,
            compression_level=compression_level,
        )
        video_dir = osp.join(down_dir, local_subdir) if local_subdir else down_dir

        video_folders.append(video_dir)
    
    logger.info('Successfully downloaded alert %s to %s', alert_id, download_dir)
    return video_folders


def download_alerts(alert_list, download_dir=LOCAL_STORAGE_DIR, alert_type=None, env='production', downscale=False, sync_s3_uri=None, compression_level=1):
    """Download multiple alerts.

    Args:
        alert_list (list): list of alert IDs, avids, or aaids
        download_dir (str): path to download directory
        alert_type (str|None): 'alert_id', 'avid', or 'aaid'. If None, infer from value.
        env (str): 'production' or 'staging'
        downscale (bool): whether to downscale downloaded mp4 videos
        sync_s3_uri (str|None): optional destination S3 URI for final sync
        compression_level (int): compression profile level (1, 2, or 3)
    """
    logger.info(
        'Starting download_alerts: total=%d, download_dir=%s, env=%s, downscale=%s',
        len(alert_list),
        download_dir,
        env,
        downscale,
    )
    all_video_folders = []
    for alert_id in alert_list:
        resolved_alert_type = alert_type if alert_type is not None else infer_alert_type(alert_id)
        logger.info('Processing %s as %s', alert_id, resolved_alert_type)
        try:
            downloaded_folders = download_alert(
                alert_id,
                download_dir,
                env=env,
                input_type=resolved_alert_type,
                downscale=downscale,
                compression_level=compression_level,
            )
            all_video_folders.extend(downloaded_folders)
        except Exception as e:
            logger.error('Failed to download %s: %s', alert_id, str(e))
            continue

    if sync_s3_uri:
        logger.info('Starting final sync to %s', sync_s3_uri)
        for folder in all_video_folders:
            folder_name = osp.basename(osp.normpath(folder))
            target_uri = sync_s3_uri.rstrip('/') + f'/{folder_name}/'
            sync_folder_to_s3(folder, target_uri)

    logger.info('Completed download_alerts: downloaded_folders=%d', len(all_video_folders))


def pull_from_s3(destination_dir: str = LOCAL_STORAGE_DIR, s3_uri: str = s3_sync_path, ids: list | None = None) -> None:
    """Download folders from S3 to local destination directory.

    Args:
        destination_dir: local directory to sync into
        s3_uri: source S3 URI (e.g. s3://bucket/prefix/)
        ids: optional list of folder names to download; if None download all
    """
    if not osp.exists(destination_dir):
        os.makedirs(destination_dir)

    if ids is None:
        logger.info('Syncing all folders from %s to %s', s3_uri, destination_dir)
        cmd = ['aws', 's3', 'sync', s3_uri.rstrip('/') + '/', destination_dir]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.error('aws s3 sync failed with exit code %d', result.returncode)
        else:
            logger.info('pull_from_s3 complete')
        return

    bucket, prefix = parse_s3_uri(s3_uri)
    prefix = prefix.rstrip('/') + '/' if prefix else ''

    s3_client = boto3.client('s3')
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter='/')

    available_ids = []
    for page in pages:
        for cp in page.get('CommonPrefixes', []):
            folder_name = cp['Prefix'].rstrip('/').split('/')[-1]
            available_ids.append(folder_name)

    if not available_ids:
        logger.warning('No folders found under s3://%s/%s', bucket, prefix)
        return

    targets = [i for i in available_ids if i in ids]
    missing = [i for i in ids if i not in available_ids]
    if missing:
        logger.warning('IDs not found in S3: %s', missing)

    logger.info('Pulling %d/%d folders from s3://%s/%s to %s', len(targets), len(available_ids), bucket, prefix, destination_dir)

    for folder_name in targets:
        folder_s3_path = f's3://{bucket}/{prefix}{folder_name}/'
        local_folder = osp.join(destination_dir, folder_name)
        cmd = ['aws', 's3', 'sync', folder_s3_path, local_folder]
        logger.info('Syncing %s -> %s', folder_s3_path, local_folder)
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            logger.error('aws s3 sync failed for %s: %s', folder_name, result.stderr.decode('utf-8', errors='ignore'))
        else:
            logger.info('Downloaded %s', folder_name)

    logger.info('pull_from_s3 complete: %d folders downloaded', len(targets))


if __name__ == '__main__':
    logformat = '%(asctime)s - %(levelname)-07s - %(name)-025s - %(message)s'
    logging.basicConfig(format=logformat, stream=sys.stdout, level=logging.INFO)
    
    # Example usage
    # alerts = ['alert1', 'alert2', 'alert3']
    # download_alerts(alerts, '/path/to/download', alert_type='alert_id')

    avids = ['a90c7bc4-8ea0-4a0b-8e48-b7835c02c0f8','4047fa8b-b0d7-4ac6-b248-f7cf6b5894b1']
    download_alerts(avids, downscale=True, sync_s3_uri=s3_sync_path)
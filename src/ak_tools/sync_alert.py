import json
import os
import os.path as osp
import sys
import logging
import subprocess
import boto3
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
AVC_API_ENDPOINT = 'https://analytics-kpis.netradyne.info/avc_api'


logger = logging.getLogger(__name__)


def downscale_video(video_path, output_path, resolution='480', fps=20):
    """Downscale video to specified resolution and fps using ffmpeg.
    
    Args:
        video_path (str): path to input video
        output_path (str): path to output video
        resolution (str): target height in pixels (480, 720, etc.)
        fps (int): target frames per second
    """
    if not os.path.exists(video_path):
        logger.warning('Video file not found: %s', video_path)
        return False
    
    try:
        # Check if ffmpeg is available
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode != 0:
            logger.warning('ffmpeg not available, skipping downscaling')
            return False
            
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vf', f'scale=-2:{resolution}:flags=fast_bilinear,fps={fps}',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
            '-c:a', 'copy',
            '-y', output_path
        ]
        logger.info('Downscaling %s to %sp@%sfps', video_path, resolution, fps)
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        
        if result.returncode != 0:
            logger.error('ffmpeg error: %s', result.stderr.decode('utf-8', errors='ignore'))
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            os.remove(video_path)
            os.rename(output_path, video_path)
            logger.info('Downscaling complete: %s', video_path)
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


def download_data(bucket, prefix, down_dir, downscale=False):
    """Download data from S3.

    Args:
        bucket (str): bucket name
        prefix (str): prefix to download
        down_dir (str): path to directory for download
        downscale (bool): whether to downscale downloaded mp4 videos
    """
    logger.info('Syncing data from %s/%s to %s', bucket, prefix, down_dir)
    prefix = str(prefix).rstrip(osp.sep)
    if not osp.exists(osp.join(down_dir, prefix)):
        os.makedirs(osp.join(down_dir, prefix))
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
        if not osp.exists(osp.join(down_dir, prefix)):
            os.makedirs(osp.join(down_dir, prefix))
        file_path = osp.join(down_dir, prefix, filename)
        bucket_obj.download_file(obj.key, file_path)
        
        # Downscale video files to 480p at 20fps when explicitly requested
        if downscale and filename.endswith('.mp4'):
            downscale_video(file_path, file_path + '.tmp.mp4')

def download_alert(alert_id, download_dir, env='production', input_type='alert_id', downscale=False):
    """Download alert data from S3.

    Args:
        alert_id (str): alert ID, avid, aaid, etc.
        download_dir (str): path to download directory
        env (str): 'production' or 'staging'
        input_type (str): type of input - 'alert_id', 'avid', 'aaid'
        downscale (bool): whether to downscale downloaded mp4 videos

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
    for s3_path in s3_path_list:
        s3_tokens = s3_path.split('/')
        parent_s3_bucket = s3_tokens[0]
        s3_prefix = '/'.join(s3_tokens[1:])
        down_dir = osp.join(download_dir, parent_s3_bucket)
        
        download_data(parent_s3_bucket, s3_prefix, down_dir=down_dir, downscale=downscale)
        video_dir = osp.join(down_dir, s3_prefix)

        video_folders.append(video_dir)
    
    logger.info('Successfully downloaded alert %s to %s', alert_id, download_dir)
    return video_folders


def download_alerts(alert_list, download_dir, alert_type='alert_id', env='production', downscale=False):
    """Download multiple alerts.

    Args:
        alert_list (list): list of alert IDs, avids, or aaids
        download_dir (str): path to download directory
        alert_type (str): 'alert_id', 'avid', or 'aaid'
        env (str): 'production' or 'staging'
        downscale (bool): whether to downscale downloaded mp4 videos
    """
    for alert_id in alert_list:
        try:
            download_alert(
                alert_id,
                download_dir,
                env=env,
                input_type=alert_type,
                downscale=downscale,
            )
        except Exception as e:
            logger.error('Failed to download %s: %s', alert_id, str(e))
            continue


if __name__ == '__main__':
    logformat = '%(asctime)s - %(levelname)-07s - %(name)-025s - %(message)s'
    logging.basicConfig(format=logformat, stream=sys.stdout, level=logging.INFO)
    
    # Example usage
    # alerts = ['alert1', 'alert2', 'alert3']
    # download_alerts(alerts, '/path/to/download', alert_type='alert_id')

    avids = ['a90c7bc4-8ea0-4a0b-8e48-b7835c02c0f8','4047fa8b-b0d7-4ac6-b248-f7cf6b5894b1']
    download_alerts(avids, './temp/', alert_type='avid', downscale=True)
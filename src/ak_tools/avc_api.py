"""AVC API client for querying alert data and retrieving video information."""

import json
import logging
from functools import partial

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import multiprocessing as mp
from tqdm import tqdm

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

AVC_API_ENDPOINT = 'https://analytics-kpis.netradyne.info/avc_api'


def requests_retry_session(retries=5, backoff_factor=1,
                           status_forcelist=(400, 429, 500, 502, 503, 504),
                           session=None):
    """Define the retry strategy for requests.
    
    Adapted from `here <https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/#combining-timeouts-and-retries>_`
    and `here <https://www.peterbe.com/plog/best-practice-with-retries-with-requests>_`

    Args:
        retries (int): no. of retry attempts
        backoff_factor (float): used to define wait time between retries. The sequence come from
        the equation `{backoff factor} * (2 ** ({number of total retries} - 1))`
        status_forcelist (tuple of int): response codes on which retry will be attempted
        session (requests.Session): session for requests

    Returns:
        session (requests.Session): session for requests
    """
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


def query_api(input_data, env):
    """Main function which calls the AVC API.

    Args:
        input_data (dict): Single key dictionary.
                           Supported keys - [alert_id, aaid, avid, avsid, request_id]
        env : production/staging. Will be converted to primary/secondary as required by avc_api

    Returns:
        response (dict): Structure - {
                                        'msg': <Response message from AVC API,
                                        'aaid': <Will be supplied if input key is alert_id or aaid>,
                                        'avid': [list of corresponding avids],
                                        'avsid': corresponding avsid,
                                        'sequence_pos': [list of sequence positions of videos],
                                        's3_path': path to s3_folder of sequence,
                                      }
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


def sync_data(input_id, input_type, env):
    """Main function to call AVC API, download data and create symlinks.

    Args:
        input_id: The ID to query (alert_id, aaid, avid, avsid, or request_id)
        input_type (str): Type of input (e.g., 'alert_id', 'aaid', 'avid', 'avsid', 'request_id')
        env (str): 'production'/'staging'
        
    Returns:
        pd.Series: Result from API query
    """
    if input_id is None:
        return pd.Series()
    
    input_data = {input_type: input_id}
    
    try:
        result = query_api(input_data, env)
    except Exception as e:
        logger.error('Error while processing input %s: %s', input_id, e)
        result = pd.Series()
    
    result.update(input_data)
    return pd.Series(result)


def process_ids_from_file(input_file, input_type='alert_id', env='production', 
                          num_processes=9, tail_lines=None, output_file=None):
    """Process IDs from a file using multiprocessing.
    
    Args:
        input_file (str): Path to CSV file containing IDs (assumes single column with header 'alert_id' or no header)
        input_type (str): Type of input in the file (default: 'alert_id')
        env (str): Environment - 'production' or 'staging' (default: 'production')
        num_processes (int): Number of parallel processes (default: 9)
        tail_lines (int): Only process last N lines from file (optional)
        output_file (str): Path to save results CSV (default: 'alert_df_results.csv')
        
    Returns:
        pd.DataFrame: Results from API queries
    """
    # Read the input file
    try:
        df = pd.read_csv(input_file, header=None, names=[input_type])
    except Exception as e:
        logger.error('Error reading file %s: %s', input_file, e)
        raise
    
    # Optionally take only last N lines
    if tail_lines is not None:
        df = df.tail(tail_lines)
        logger.info(f'Processing last {tail_lines} lines from {input_file}')
    else:
        logger.info(f'Processing all {len(df)} lines from {input_file}')
    
    # Get unique IDs
    ids = df[input_type].unique()
    logger.info(f'Processing {len(ids)} unique IDs')
    
    # Process in parallel
    fun = partial(sync_data, input_type=input_type, env=env)
    with mp.Pool(processes=num_processes) as pool:
        out_list = list(tqdm(pool.imap(fun, ids), total=len(ids)))
    
    # Combine results
    result_df = pd.concat(out_list, axis=1).T
    
    # Save results
    if output_file is None:
        output_file = f'{input_type}_results.csv'
    result_df.to_csv(output_file)
    logger.info(f'Results saved to {output_file}')
    
    return result_df

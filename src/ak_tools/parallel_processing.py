"""
README:
copy this into the notebok.


"""


from concurrent.futures import ProcessPoolExecutor
from tqdm.auto import tqdm
import os
import json

def process_single_item(item):
    """
    Ensure this function is defined at the top level of your script/module
    so that it is 'picklable' for the multiprocessing workers.
    """
    # Replace this with your actual logic (e.g., extract_ld_and_yaw)
    return item

def parallel_processor(
        single_item_func,
        data_list,
        output_folder,
        chunk_size=2000,
        max_workers=None, # Defaults to os.cpu_count()
        to_return=False,
):
    os.makedirs(output_folder, exist_ok=True)
    chunks = [data_list[i:i + chunk_size] for i in range(0, len(data_list), chunk_size)]
    
    print(f"Processing {len(data_list)} items with {max_workers or os.cpu_count()} processes...")

    # Open the executor once to avoid overhead of creating pools repeatedly
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for i, chunk in enumerate(tqdm(chunks, desc="Processing Batches")):
            
            # Map the function over the current chunk
            # list() here forces execution, which is fine for individual chunks
            results = list(executor.map(single_item_func, chunk))
            
            # Pair results back with the original items
            result_dict = {item: result for item, result in zip(chunk, results)}
            
            # Save the batch
            output_path = os.path.join(output_folder, f"batch_{i:04d}.json")
            with open(output_path, "w") as f:
                json.dump(result_dict, f)

    print("Processing complete.")

    if to_return:
        combined_results = {}
        for i in range(len(chunks)):
            output_path = os.path.join(output_folder, f"batch_{i:04d}.json")
            with open(output_path, "r") as f:
                batch_data = json.load(f)
            combined_results.update(batch_data)
        return combined_results

# Usage:
# parallel_processor(avids, extract_ld_and_yaw, "./output_data")
import os
import threading
import queue
import time
from test_movie import create_video_from_json, load_json
from uuid import uuid4

num_cores = os.cpu_count()
num_workers = num_cores if num_cores else 4 

print(f"Detected {num_cores} CPU cores, setting {num_workers} workers.")

task_queue = queue.Queue()

def process_task(task_id, json_data):
    print(f"Processing task {task_id}...")

    try:
        file_name = f"{str(uuid4())[:4]}.mp4"
        response = create_video_from_json(json_data, file_name)
        print(f"Task {task_id} completed: {response}")
    except Exception as e:
        print(f"Error processing task {task_id}: {str(e)}")

def worker(worker_id):
    while True:
        task_id, json_data = task_queue.get()
        if task_id is None:
            print(f"Worker {worker_id} exiting...")
            break
        process_task(task_id, json_data)
        task_queue.task_done()


def add_task(json_data):
    task_id = f"task_{int(time.time())}"
    print(f"Adding {task_id} to the queue...")
    task_queue.put((task_id, json_data))

workers = []
for i in range(num_workers):
    t = threading.Thread(target=worker, args=(i,))
    t.start()
    workers.append(t)

json_data_example = load_json('./example.json')

start_time = time.time()

for _ in range(1):
    add_task(json_data_example)

task_queue.join()

for _ in range(num_workers):
    task_queue.put((None, None))

for w in workers:
    w.join()

end_time = time.time()

total_time = end_time - start_time
print(f"All tasks are processed. Total time taken: {total_time:.2f} seconds.")

from datetime import datetime

print("Writing the file...")

with open("/mnt/d/Developer/Shell scripting/file.txt", "a") as f:  # "a" = append mode (does not erase old content)
    curr_time = datetime.now().strftime('%d-%m-%y %H:%M:%S')
    f.write(f'hello from cron {curr_time} \n')  # "\n" ensures each entry is on a new line

print("Done !!")
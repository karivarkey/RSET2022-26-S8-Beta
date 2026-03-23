from app.ml.task_extractor.task_extractor import extract_tasks

text = "Please submit the report by Monday. Also schedule a meeting tomorrow."

tasks = extract_tasks(text)
print(tasks)
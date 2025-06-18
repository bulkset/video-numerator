import cv2
from ultralytics import YOLO

# Загрузка лёгкой модели YOLOv8
model = YOLO("yolov8n.pt")  # Можно заменить на yolov8s.pt для большей точности

# Открытие камеры (0 — встроенная)
cap = cv2.VideoCapture(0)

# Общий счёт
total_count = 0
tracked_ids = set()

print("Нажми 'q' для выхода...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Ошибка камеры!")
        break

    # Детекция и трекинг
    results = model.track(source=frame, persist=True, verbose=False, tracker="bytetrack.yaml")

    boxes = results[0].boxes
    annotated = results[0].plot()

    # Получение ID объектов
    if boxes.id is not None:
        ids = boxes.id.int().tolist()
        for obj_id in ids:
            if obj_id not in tracked_ids:
                tracked_ids.add(obj_id)
                total_count += 1

    # Отображение счётчика
    cv2.putText(
        annotated,
        f"Total: {total_count}",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (0, 0, 255),
        3
    )

    cv2.imshow("Bread/Egg Counter", annotated)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
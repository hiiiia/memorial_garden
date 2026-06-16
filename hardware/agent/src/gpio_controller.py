# import RPi.GPIO as GPIO
import time

def setup_gpio():
    print("🔧 GPIO 초기화 중... (현재는 React 기반이므로 비활성화 상태입니다)")
    # GPIO.setmode(GPIO.BCM)
    # GPIO.setup(18, GPIO.OUT)

def run_gpio_controller():
    setup_gpio()
    try:
        while True:
            # 상태 모니터링 로직 (예: 시스템 상태에 따라 LED 색상 변경)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
        # GPIO.cleanup()

if __name__ == "__main__":
    run_gpio_controller()
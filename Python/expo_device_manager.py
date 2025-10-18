"""Expo 데모 장치를 제어하는 관리자 모듈."""

from __future__ import annotations

import threading
import time
import serial

DEFAULT_SERIAL_BAUDRATE = 115200
DEFAULT_SERIAL_TIMEOUT = 1
DEFAULT_SERIAL_WRITE_TIMEOUT = 1

# --- 환경 기본값
DEFAULT_SYNC_INTERVAL = 10  # Minutes
DEFAULT_EARTHQUAKE_DURATION = 5  # Seconds


class DeviceManager:
    """시리얼 기반 Expo 장치를 묶어서 제어하는 헬퍼."""

    def __init__(self):
        self.obj_6: int | None = None
        self.obj_7: int | None = None
        self.obj_8: list[int] = []
        self.obj_9: int | None = None
        self.dot_matrix_current_state = ""
        self.lock = threading.Lock()
        # 지진 루틴이 진행 중인지 공유하기 위한 이벤트
        self.earthquake_active = threading.Event()
        self.port_obj: list[serial.Serial | None] = []

    def connect(self, ports: list[str]):
        """시리얼 포트를 열고 장치 핸들을 캐싱."""
        self.port_obj = [None] * len(ports)
        try:
            for i, port in enumerate(ports):
                ser = serial.Serial(
                    port=port,
                    baudrate=DEFAULT_SERIAL_BAUDRATE,
                    timeout=DEFAULT_SERIAL_TIMEOUT,
                    write_timeout=DEFAULT_SERIAL_WRITE_TIMEOUT,
                )
                self.port_obj[i] = ser
        except Exception as e:
            print(f"포트 연결 중 오류: {e}")
            raise
    ##추가 구문
    def activate(self):
        """연결된 장치에 'q' 신호를 보내 타입을 수신하고 매핑."""
        print("장치 안정화 중...")

        time.sleep(2) # 최소 대기

      # 모든 Dot Matrix에 '통신중' 표시
        for i, ser in enumerate(self.port_obj):
            if ser:
                try:
                    ser.write(b'c')  # '통신중' 명령
                except:
                    pass
    
        time.sleep(3) # 나머지 안정화

        for i, ser in enumerate(self.port_obj):
            if ser is None:
                continue
            try:
                ser.write(b'q')
                data = ser.read(1)
                time.sleep(1)

                if data == b'6':
                    self.obj_6 = i
                elif data == b'7':
                    self.obj_7 = i
                elif data == b'8':
                    self.obj_8.append(i)
                elif data == b'9':
                    self.obj_9 = i
            except Exception as e:
                print(f"장치 활성화 오류 (포트 {i}): {e}")

        print(f"장치 매핑 완료: obj_6={self.obj_6}, obj_7={self.obj_7}, "
              f"obj_8={self.obj_8}, obj_9={self.obj_9}")

    def disconnect(self):
        """모든 시리얼 포트 닫기 전 시스템 리셋."""
        print("장치 종료 준비 중...")
        
        # 지진 장치 리셋 (Type 7)
        if self.obj_7 is not None and self.port_obj[self.obj_7]:
            try:
                self.port_obj[self.obj_7].write(b's')
                time.sleep(0.1)  # 명령 전송 대기
                print("지진 장치 리셋 완료")
            except Exception as e:
                print(f"지진 장치 리셋 오류: {e}")
        
        # 모든 포트 닫기
        for ser in self.port_obj:
            if ser and ser.is_open:
                try:
                    ser.close()
                except Exception as e:
                    print(f"포트 닫기 오류: {e}")
        
        print("모든 포트 연결 해제됨")

    def reset_environment(self):
        """초기 상태: LED 스트립 GREEN, Dot Matrix '통신중'."""
        print("환경 초기화 중...")
        self.set_dot_matrix("통신중")
        self.set_led("GREEN")
        self.reset_earthquake_system()  # 's' 명령 사용
        print("환경 초기화 완료")

    def reset_earthquake_system(self):
        """시스템 리셋: 지진 중지 + 복구 플래그 해제 ('s' 명령)."""
        if self.obj_7 is None:
            return

        try:
            self.port_obj[self.obj_7].write(b's')  # System Reset 명령
            self.earthquake_active.clear()
            print("지진 시스템 리셋 (복구 플래그 해제)")
        except Exception as e:
            print(f"시스템 리셋 오류: {e}")

    def set_dot_matrix(self, text: str):
        """Dot Matrix(type 8)에 텍스트 표시."""
        if not self.obj_8:
            print("Dot Matrix 장치가 할당되지 않음")
            return

        command_map = {
            "통신중": b'c',
            "통신불가": b'n',
            "복구중": b'v',
        }

        cmd = command_map.get(text)
        if cmd is None:
            print(f"알 수 없는 Dot Matrix 텍스트: {text}")
            return

        with self.lock:
            for idx in self.obj_8:
                if self.port_obj[idx]:
                    try:
                        self.port_obj[idx].write(cmd)
                    except Exception as e:
                        print(f"Dot Matrix 명령 전송 오류 (포트 {idx}): {e}")

        self.dot_matrix_current_state = text
        print(f"Dot Matrix 상태 변경: {text}")

    def set_led(self, color: str):
        """LED 스트립(type 6, 7)의 색상 설정."""
        color_map = {
            "GREEN": b'g',
            "RED": b'r',
        }

        cmd = color_map.get(color.upper())
        if cmd is None:
            print(f"알 수 없는 LED 색상: {color}")
            return

        indices = []
        if self.obj_6 is not None:
            indices.append(self.obj_6)
        if self.obj_7 is not None:
            indices.append(self.obj_7)

        for idx in indices:
            if self.port_obj[idx]:
                try:
                    self.port_obj[idx].write(cmd)
                except Exception as e:
                    print(f"LED 색상 명령 전송 오류 (포트 {idx}): {e}")

        print(f"LED 스트립 상태 변경: {color}")

    def start_earthquake(self):
        """지진 효과 시작 (CR Servo ON, type 7)."""
        if self.obj_7 is None:
            print("지진 장치(Type 7)가 할당되지 않음")
            return

        try:
            self.port_obj[self.obj_7].write(b'1')
            self.earthquake_active.set()
            print("지진 발생")
        except Exception as e:
            print(f"지진 시작 오류: {e}")


    def stop_earthquake(self):
        """지진 효과 중지 (CR Servo OFF, type 7)."""
        if self.obj_7 is None:
            return

        try:
            self.port_obj[self.obj_7].write(b'0')
            self.earthquake_active.clear()
            print("지진 효과 중지 (복구 완료)")
        except Exception as e:
            print(f"지진 중지 오류: {e}")

    def wait_for_tof_trigger(self):
        """ToF 센서(type 9)가 'o' 신호를 보낼 때까지 대기."""
        if self.obj_9 is None:
            print("ToF 센서(Type 9)가 할당되지 않음")
            return

        print("ToF 센서 트리거 대기 중...")
        while True:
            try:
                data = self.port_obj[self.obj_9].read(1)
                if data == b'o':
                    print("ToF 센서 트리거 감지!")
                    return
            except Exception as e:
                print(f"ToF 센서 읽기 오류: {e}")
                time.sleep(0.1)
            time.sleep(0.1)

    def demo_thread(self):
        """데모 시퀀스 스레드 수정 (시나리오 순서 반영)."""
        assert self.obj_9 is not None,  "센서(Type 9) 포트 미할당"

        # 1단계: 지진 발생 (약 3.5초간)
        print("1단계: 지진 발생")
        time.sleep(3.5)  # 시작 후 지진 시작 딜레이 (3.5초) 
        self.start_earthquake()  # 지진 시작 + 서보 DOWN
         
        # 2단계: 통신 단절 표시
        time.sleep(2)  # 통신 단절 변경 딜레이 (2초)
        print("2단계: 통신 단절")
        self.set_dot_matrix("통신불가")
        self.set_led("RED")

        # 3단계: 지진 중지
        print("3단계: 통신불가 상태 유지 및 5초뒤 지진 중지 (3.5초)")
        time.sleep(3.5) #중지 전 3.5초 딜레이
        self.stop_earthquake()  # 지진 중지 + 서보 UP
        
        # 4단계: ToF 센서 트리거 대기 (RC 카 도착)
        print("4단계: RC 카 도착 대기")
        self.wait_for_tof_trigger()

        # 5단계: 통신 복구 중
        print("5단계: 통신 복구 중")
        self.set_dot_matrix("복구중")

        # 6단계: 복구 완료 (5초 대기) 통신중 전환은 몇초로 할까 
        time.sleep(5)
        print("6단계: 통신 복구 완료")
        self.set_dot_matrix("통신중")
        self.set_led("GREEN")

        print("데모 시퀀스 완료")

    def start_demo_sequence(self):
        """데모 시퀀스를 별도 스레드로 시작."""
        thread = threading.Thread(target=self.demo_thread, daemon=True)
        thread.start()
        print("데모 시퀀스 스레드 시작됨")

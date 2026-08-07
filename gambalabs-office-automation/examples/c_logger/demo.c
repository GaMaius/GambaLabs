#include <stdio.h>
#include "gamba_log.h"

int main() {
    printf("=== C/C++ gamba_log.h 테스트 실행 ===\n");
    
    // 1줄 단순 명령 방식 (C/C++)
    gamba_log("정확도(%)=88.5, SNR(dB)=-10, 비고=C_Baseline", "output/c_experiment_tracker.txt");
    gamba_log("정확도(%)=91.2, SNR(dB)=-15, 비고=C_Tuning", "output/c_experiment_tracker.txt");
    gamba_log("정확도(%)=94.5, SNR(dB)=-20, 비고=C_Quantized", "output/c_experiment_tracker.txt");

    // 아두이노 / 키-값 세분화 누적 방식 (Arduino/ESP32)
    gamba_log_kv("정확도(%)", "96.1");
    gamba_log_kv_num("SNR(dB)", -22.5);
    gamba_log_kv("비고", "Arduino_KWS_Test");
    gamba_log_commit("output/c_experiment_tracker.txt");

    printf("=== C/C++ 테스트 성공 완료 ===\n");
    return 0;
}

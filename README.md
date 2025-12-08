# OpenBMC MCTP Tool

OpenBMC에서 MCTP (Management Component Transport Protocol) 메시지를 DBus를 통해 전송할 수 있는 Python 기반 서비스입니다.

## 프로젝트 구성

```
openbmc-mctp/
└── meta-phosphor/
    └── recipes-phosphor/
        └── mctp/
            └── mctp-tool/
                ├── mctp_tool.py                               # MCTP DBus 서비스
                └── xyz.openbmc_project.Mctp.Tool.service      # systemd 서비스
```

## 주요 기능

Python 기반 DBus 서비스로 MCTP 메시지 송수신 기능 제공:

- **Send**: MCTP 메시지 전송
  - Signature: `yyay` (eid, msg_type, payload)
  
- **SendRecv**: MCTP 메시지 송신 및 응답 수신
  - Signature: `yyayq` (eid, msg_type, payload, timeout_ms)

### DBus Interface

**Service**: `xyz.openbmc_project.Mctp.Tool`  
**Object Path**: `/xyz/openbmc_project/mctp/tool`  
**Interface**: `xyz.openbmc_project.Mctp.Tool`

**Methods**:
- `Send(yyay) -> ()`
  - `eid`: uint8 - Destination EID
  - `msg_type`: uint8 - MCTP message type (0x01=PLDM, 0x7E=VDM, etc.)
  - `payload`: array of bytes - Message payload (Header + Body)

- `SendRecv(yyayq) -> (ay)`
  - `eid`: uint8 - Destination EID
  - `msg_type`: uint8 - MCTP message type
  - `payload`: array of bytes - Message payload
  - `timeout_ms`: uint16 - Timeout in milliseconds
  - Returns: array of bytes - Response payload

## 지원 플랫폼

- Intel Granite Rapids-SP (GNR-SP)
- AMD Turin
- AST2600 기반 BMC

---

## 배포 가이드

### 1. BMC 환경 확인

```bash
# BMC에 SSH 접속
ssh root@<BMC_IP>

# Python 환경 확인
python3 --version
python3 -c "import dbus; import dbus.service; from gi.repository import GLib; print('✅ Python 패키지 OK')"

# MCTP 커널 모듈 확인
lsmod | grep mctp
ls /sys/class/net/ | grep mctp
```

### 2. 파일 전송

```bash
# 워크스테이션에서 실행
cd meta-phosphor/recipes-phosphor/mctp/mctp-tool

# mctp_tool.py 전송
scp mctp_tool.py root@<BMC_IP>:/usr/bin/

# systemd 서비스 파일 전송
scp xyz.openbmc_project.Mctp.Tool.service root@<BMC_IP>:/lib/systemd/system/
```

### 3. BMC에서 설정

```bash
# 1. 실행 권한 부여
chmod +x /usr/bin/mctp_tool.py

# 2. DBus 정책 파일 생성
cat > /etc/dbus-1/system.d/xyz.openbmc_project.Mctp.Tool.conf << 'EOF'
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="root">
    <allow own="xyz.openbmc_project.Mctp.Tool"/>
    <allow send_destination="xyz.openbmc_project.Mctp.Tool"/>
  </policy>
  <policy context="default">
    <allow send_destination="xyz.openbmc_project.Mctp.Tool"/>
  </policy>
</busconfig>
EOF

# 3. systemd 서비스 활성화
systemctl daemon-reload
systemctl enable xyz.openbmc_project.Mctp.Tool
systemctl start xyz.openbmc_project.Mctp.Tool

# 4. 서비스 상태 확인
systemctl status xyz.openbmc_project.Mctp.Tool
```

### 4. 테스트

```bash
# DBus 서비스 확인
busctl list | grep Mctp

# 인터페이스 확인
busctl introspect xyz.openbmc_project.Mctp.Tool /xyz/openbmc_project/mctp/tool

# Send 메서드 테스트 (MCTP 하드웨어 없으면 에러 예상)
busctl call xyz.openbmc_project.Mctp.Tool /xyz/openbmc_project/mctp/tool \
  xyz.openbmc_project.Mctp.Tool Send yyay 8 1 4 128 0 2 1
```

---

## 트러블슈팅

### 서비스 로그 확인
```bash
journalctl -u xyz.openbmc_project.Mctp.Tool -n 100
journalctl -u xyz.openbmc_project.Mctp.Tool -f
```

### DBus 권한 문제
```bash
# DBus 서비스 목록 확인
dbus-send --system --print-reply --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus org.freedesktop.DBus.ListNames
```

### MCTP 하드웨어 확인
```bash
# MCTP 네트워크 인터페이스
ip link show | grep mctp

# MCTP 라우팅 테이블
cat /proc/net/mctp/routes
```

---

## REST API 연동

이 DBus 서비스를 Redfish REST API로 노출하려면 [bmcweb-mctp-restful-api](https://github.com/your-org/bmcweb-mctp-restful-api) 레포지토리를 참고하세요.

---

## 아키텍처

```
┌─────────────────────────────────────────┐
│  mctp_tool.py (DBus Service)            │
│  - Send(eid, msg_type, payload)         │
│  - SendRecv(eid, msg_type, payload, ms) │
└──────────────┬──────────────────────────┘
               │ AF_MCTP Socket
               ▼
┌─────────────────────────────────────────┐
│  Linux Kernel MCTP Stack                │
│  - /sys/class/net/mctpi2c*              │
│  - /proc/net/mctp/routes                │
└──────────────┬──────────────────────────┘
               │ I2C/I3C/PCIe
               ▼
┌─────────────────────────────────────────┐
│  MCTP Endpoint Devices                  │
│  (NVMe, GPU, Switch, etc.)              │
└─────────────────────────────────────────┘
```

---

## 참고 자료

- [OpenBMC 공식 문서](https://github.com/openbmc/docs)
- [MCTP Base Specification](https://www.dmtf.org/standards/pmci)
- [PLDM Specification](https://www.dmtf.org/standards/pmci)

## 라이선스

Apache 2.0

import asyncio
import time
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer
from aiortc.contrib.signaling import object_to_string, object_from_string
from cryptography.fernet import Fernet

# --- 加密金鑰（與 caller 相同） ---
FERNET_KEY = b"key"
fernet = Fernet(FERNET_KEY)

# --- 狀態追蹤變數 ---
has_connected = False
has_input = False
active_channel = None

# --- 顯示連線方式 ---
async def print_connection_info(pc: RTCPeerConnection):
    try:
        stats = await pc.getStats()
        selected_pair = None
        for stat in stats.values():
            if stat.type == "transport" and hasattr(stat, "selectedCandidatePairId"):
                selected_pair = stats.get(stat.selectedCandidatePairId)
                break
        if selected_pair:
            local = stats.get(selected_pair.localCandidateId)
            remote = stats.get(selected_pair.remoteCandidateId)
            print("Connected via:")
            print(f"Local: {local.candidateType} {local.address}:{local.port}")
            print(f"Remote: {remote.candidateType} {remote.address}:{remote.port}")
            if "relay" in (local.candidateType, remote.candidateType):
                print("Using TURN relay")
            elif "srflx" in (local.candidateType, remote.candidateType):
                print("NAT traversal via STUN (srflx)")
            elif "host" in (local.candidateType, remote.candidateType):
                print("Local network direct (host)")
            else:
                print("Other connection type")
        else:
            print("No selected candidate pair found")
    except Exception as e:
        print("Failed to get connection info:", e)

# --- 測速功能 ---
async def speed_test(channel):
    print("Starting speed test: sending 20MB of data...")
    data = b"x" * (20 * 1024 * 1024)
    start_time = time.perf_counter()
    channel.send(data)
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    speed = 20 / elapsed if elapsed > 0 else 0
    print(f"Sent 20MB in {elapsed:.2f} seconds ({speed:.2f} MB/s)")

# --- 聊天輸入 ---
async def chat_input(channel):
    loop = asyncio.get_event_loop()
    await asyncio.sleep(0.1)
    while True:
        msg = await loop.run_in_executor(None, input, "You: ")
        if msg.strip() == "speed_test()":
            await speed_test(channel)
        elif channel.readyState == "open":
            channel.send(msg)

# --- Channel 設定 ---
def setup_channel(channel, pc):
    global has_connected, active_channel
    active_channel = channel

    @channel.on("open")
    def on_open():
        print("Data channel is open. Start chatting.")
        asyncio.create_task(print_connection_info(pc))
        asyncio.create_task(chat_input(channel))

    @channel.on("message")
    def on_message(message):
        global has_connected
        has_connected = True
        if isinstance(message, bytes):
            size_mb = len(message) / (1024 * 1024)
            print(f"\nReceived binary data: {size_mb:.2f} MB")
        else:
            print(f"\nPeer: {message}")

# --- 主程式 ---
async def run():
    global has_connected, has_input, active_channel

    config = RTCConfiguration(iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302")
    ])
    pc = RTCPeerConnection(configuration=config)

    @pc.on("datachannel")
    def on_datachannel(channel):
        setup_channel(channel, pc)

    encrypted_offer = input("Paste encrypted SDP offer:\n")
    decrypted_offer = fernet.decrypt(encrypted_offer.encode()).decode()
    await pc.setRemoteDescription(object_from_string(decrypted_offer))

    await pc.setLocalDescription(await pc.createAnswer())
    sdp_string = object_to_string(pc.localDescription)
    encrypted_sdp = fernet.encrypt(sdp_string.encode()).decode()

    print("\n=== Encrypted SDP (send to caller) ===")
    print(encrypted_sdp)
    print("=== End of Encrypted SDP ===\n")

    while True:
        await asyncio.sleep(1)
        if has_connected and not has_input and active_channel:
            asyncio.create_task(chat_input(active_channel))
            has_input = True

if __name__ == "__main__":
    asyncio.run(run())

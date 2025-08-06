import asyncio
import time
from aiortc import (
    RTCPeerConnection, RTCConfiguration, RTCIceServer,
)
from aiortc.contrib.signaling import object_to_string, object_from_string
from cryptography.fernet import Fernet

FERNET_KEY = b"key"
fernet = Fernet(FERNET_KEY)

# --- Utility Functions ---

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
    except Exception as e:
        print("Failed to get connection info:", e)

async def speed_test(channel):
    print("Starting speed test: sending 20MB of data...")
    data = b"x" * (20 * 1024 * 1024)
    start_time = time.perf_counter()
    channel.send(data)
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    speed = 20 / elapsed if elapsed > 0 else 0
    print(f"Sent 20MB in {elapsed:.2f} seconds ({speed:.2f} MB/s)")

async def chat_input(channel):
    await asyncio.sleep(0.1)  # Prevent "You: " printing too early
    while True:
        msg = await asyncio.to_thread(input, "You: ")
        if msg.strip() == "speed_test()":
            await speed_test(channel)
        elif channel.readyState == "open":
            channel.send(msg)

def setup_channel(channel, pc):
    @channel.on("open")
    def on_open():
        print("Data channel is open. Start chatting.")
        asyncio.create_task(print_connection_info(pc))
        asyncio.create_task(chat_input(channel))

    @channel.on("message")
    def on_message(message):
        if isinstance(message, bytes):
            size_mb = len(message) / (1024 * 1024)
            print(f"\nReceived binary data: {size_mb:.2f} MB")
        else:
            print(f"\nPeer: {message}")

# --- Main Flow ---

async def run():
    config = RTCConfiguration(iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302")
    ])
    pc = RTCPeerConnection(configuration=config)
    channel = pc.createDataChannel("chat")
    setup_channel(channel, pc)

    await pc.setLocalDescription(await pc.createOffer())
    sdp_string = object_to_string(pc.localDescription)
    encrypted_sdp = fernet.encrypt(sdp_string.encode()).decode()

    print("\n=== Encrypted SDP (send to callee) ===")
    print(encrypted_sdp)
    print("=== End of Encrypted SDP ===\n")

    encrypted_answer = input("Paste encrypted SDP answer:\n")
    decrypted_answer = fernet.decrypt(encrypted_answer.encode()).decode()
    await pc.setRemoteDescription(object_from_string(decrypted_answer))

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run())

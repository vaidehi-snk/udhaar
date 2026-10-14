"""Serve Udhaar over HTTPS on the shop's Wi-Fi so the phone's browser allows the microphone.

    python scripts/serve_https.py
Then open https://<laptop-ip>:8443 on the phone and accept the one-time certificate warning.
"""
import datetime
import ipaddress
import socket
import sys
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CERT, KEY = ROOT / "data" / "cert.pem", ROOT / "data" / "key.pem"


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def make_cert(ip: str):
    CERT.parent.mkdir(exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "udhaar.local")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address(ip)),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(key, hashes.SHA256()))
    KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                      serialization.NoEncryption()))
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


if __name__ == "__main__":
    ip = lan_ip()
    make_cert(ip)
    print(f"\n  Open on the shop phone:  https://{ip}:8443\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8443, ssl_keyfile=str(KEY), ssl_certfile=str(CERT))

"""TLS trust: combined bundle (proxy CA + config/extra_ca) with verification on; layer-naming errors."""
import hashlib
import socket
import ssl
import subprocess
import threading

import pytest
import requests

from outreach.fetch import EXTRA_CA, FetchError, ca_bundle

EMSIGN_G1_SHA256 = "40F6AF0346A99AA1CD1D555A4E9CCE62C7F9634603EE4066 15833DC8C8D00367".replace(" ", "")


def test_ca_bundle_has_proxy_ca_and_extra_pems(tmp_path):
    base = tmp_path / "base.pem"
    base.write_text("-----BEGIN CERTIFICATE-----\nPROXYCA\n-----END CERTIFICATE-----")
    extra = tmp_path / "extra"
    extra.mkdir()
    (extra / "x.pem").write_text("# note\n-----BEGIN CERTIFICATE-----\nEXTRACA\n-----END CERTIFICATE-----\n")
    body = open(ca_bundle(extra, str(base))).read()
    assert "PROXYCA" in body and "EXTRACA" in body


def test_repo_extra_ca_is_emsign_root_with_recorded_fingerprint():
    text = (EXTRA_CA / "emsign-root-ca-g1.pem").read_text()
    der = ssl.PEM_cert_to_DER_cert("-----BEGIN" + text.split("-----BEGIN", 1)[1])
    assert hashlib.sha256(der).hexdigest().upper() == EMSIGN_G1_SHA256
    ctx = ssl.create_default_context(cafile=ca_bundle())
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert any(c["subject"] and ("emSign Root CA - G1" in str(c["subject"])) for c in ctx.get_ca_certs())


def test_untrusted_self_signed_host_still_fails(tmp_path):
    key, crt = tmp_path / "k.pem", tmp_path / "c.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(crt),
                    "-subj", "/CN=localhost", "-days", "1"], check=True, capture_output=True)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve():
        try:
            c, _ = srv.accept()
            ctx.wrap_socket(c, server_side=True).close()
        except Exception:
            pass
    threading.Thread(target=serve, daemon=True).start()
    with pytest.raises(requests.exceptions.SSLError):
        requests.get(f"https://localhost:{srv.getsockname()[1]}/", verify=ca_bundle(), timeout=5, proxies={"https": None})


def test_fetch_error_names_layer():
    e = FetchError("http", "https://x/", "HTTP status 404")
    assert e.layer == "http" and "[http]" in str(e)

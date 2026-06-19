from sqlalchemy import text

from backend.persistence.encryption import decrypt, encrypt
from backend.persistence.models import Connection, ConnectionStatus


def test_fernet_roundtrip():
    assert decrypt(encrypt("hello-token")) == "hello-token"


def test_encrypted_column_stores_ciphertext(db_session):
    secret = "super-secret-access-token"
    conn = Connection(
        connector="manual", status=ConnectionStatus.pending, access_token=secret
    )
    db_session.add(conn)
    db_session.commit()
    conn_id = conn.id

    # Raw stored value must not be the plaintext.
    raw = db_session.execute(text("SELECT access_token FROM connections")).scalar_one()
    assert raw != secret
    assert secret not in raw

    # ORM read decrypts transparently.
    db_session.expire_all()
    reloaded = db_session.get(Connection, conn_id)
    assert reloaded.access_token == secret

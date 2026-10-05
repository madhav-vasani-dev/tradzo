"""Test bootstrap: stub Firebase/Google modules so services import without credentials."""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENABLE_SCHEDULER", "false")


def _stub(name, **attrs):
    mod = sys.modules.get(name) or types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


try:  # use the real SDK when installed
    import firebase_admin  # noqa: F401
    import google.cloud.firestore_v1  # noqa: F401
except Exception:  # noqa: BLE001
    class _FF:
        def __init__(self, *a, **k):
            pass

    fa = _stub("firebase_admin", credentials=types.SimpleNamespace(Certificate=lambda *a, **k: None),
               initialize_app=lambda *a, **k: None, firestore=types.SimpleNamespace(client=lambda: None,
               SERVER_TIMESTAMP=object()), auth=types.SimpleNamespace(verify_id_token=lambda t: {}))
    _stub("firebase_admin.credentials", Certificate=lambda *a, **k: None)
    _stub("firebase_admin.firestore", client=lambda: None, SERVER_TIMESTAMP=object())
    _stub("firebase_admin.auth", verify_id_token=lambda t: {})
    _stub("google")
    _stub("google.cloud")
    _stub("google.cloud.firestore_v1", transactional=lambda f: f, Transaction=object)
    _stub("google.cloud.firestore_v1.base_query", FieldFilter=_FF)

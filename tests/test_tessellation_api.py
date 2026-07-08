"""Transactional API coverage for Cavalry tessellation bakes."""

import pytest

from engine.pfm import REGISTRY
from engine.tessellation_library import TessellationLibrary
import web.server as server


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<path d="M0 0 L100 100" fill="none" stroke="black"/>'
    '</svg>'
)


def manifest(name="My Pattern"):
    return {
        "format_version": 1,
        "name": name,
        "lattice": {"a": [100, 0], "b": [0, 100]},
        "bounds": [0, 0, 100, 100],
        "bindings": [
            {
                "layer_id": "basicShape#1",
                "attribute_id": "rotation",
                "light": 0,
                "dark": 90,
                "curve": None,
            }
        ],
    }


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = TessellationLibrary(tmp_path / "library")
    monkeypatch.setattr(server, "_tessellation_library", library, raising=False)
    yield library
    for pfm_id in list(REGISTRY):
        if pfm_id.startswith("tessellation_custom_"):
            REGISTRY.pop(pfm_id, None)


@pytest.fixture
def session_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    monkeypatch.setattr(server, "_tessellation_session_root", root, raising=False)
    return root


@pytest.fixture
def client(isolated_library, session_root):
    return server.app.test_client()


def test_complete_session_installs_and_registers(client, isolated_library):
    created = client.post("/api/tessellations/sessions", json=manifest()).get_json()
    sid = created["session_id"]
    for index in range(32):
        response = client.post(
            f"/api/tessellations/sessions/{sid}/states/{index}",
            data=SVG,
            content_type="image/svg+xml",
        )
        assert response.status_code == 200
    result = client.post(f"/api/tessellations/sessions/{sid}/finalize")
    assert result.status_code == 200
    assert result.get_json()["pattern"]["id"] == "tessellation_custom_my_pattern"
    assert "tessellation_custom_my_pattern" in REGISTRY


def test_finalize_missing_state_is_non_destructive(client, isolated_library):
    sid = client.post("/api/tessellations/sessions", json=manifest()).get_json()[
        "session_id"
    ]
    client.post(
        f"/api/tessellations/sessions/{sid}/states/0",
        data=SVG,
        content_type="image/svg+xml",
    )
    response = client.post(f"/api/tessellations/sessions/{sid}/finalize")
    assert response.status_code == 400
    assert isolated_library.list() == []


def test_duplicate_and_out_of_range_states_are_rejected(client):
    sid = client.post("/api/tessellations/sessions", json=manifest()).get_json()[
        "session_id"
    ]
    assert (
        client.post(f"/api/tessellations/sessions/{sid}/states/32", data=SVG).status_code
        == 400
    )
    assert (
        client.post(f"/api/tessellations/sessions/{sid}/states/0", data=SVG).status_code
        == 200
    )
    assert (
        client.post(f"/api/tessellations/sessions/{sid}/states/0", data=SVG).status_code
        == 409
    )


def test_expired_session_is_removed(client, session_root, monkeypatch):
    sid = client.post("/api/tessellations/sessions", json=manifest()).get_json()[
        "session_id"
    ]
    monkeypatch.setattr(server.time, "time", lambda: 7_200)
    (session_root / sid / "created_at").write_text("0")
    response = client.post(
        f"/api/tessellations/sessions/{sid}/states/0", data=SVG
    )
    assert response.status_code == 404
    assert not (session_root / sid).exists()


def test_list_returns_installed_patterns(client, isolated_library):
    isolated_library.install(manifest("Listed"), [SVG] * 32)

    response = client.get("/api/tessellations")

    assert response.status_code == 200
    assert response.get_json()["patterns"][0]["id"] == "tessellation_custom_listed"

"""Transactional API coverage for Cavalry tessellation bakes."""

import io
import shutil

import pytest
from PIL import Image

from engine import project as project_mod
from engine.pfm import REGISTRY, get as get_pfm
from engine.pfm.base import generate_items
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
    previous_custom_pfms = {
        pfm_id: pfm
        for pfm_id, pfm in REGISTRY.items()
        if pfm_id.startswith("tessellation_custom_")
    }
    yield library
    for pfm_id in list(REGISTRY):
        if pfm_id.startswith("tessellation_custom_"):
            REGISTRY.pop(pfm_id, None)
    REGISTRY.update(previous_custom_pfms)


@pytest.fixture
def session_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    monkeypatch.setattr(server, "_tessellation_session_root", root, raising=False)
    return root


@pytest.fixture
def client(isolated_library, session_root):
    return server.app.test_client()


@pytest.fixture
def complete_session(client):
    sid = client.post("/api/tessellations/sessions", json=manifest()).get_json()[
        "session_id"
    ]
    for index in range(32):
        response = client.post(
            f"/api/tessellations/sessions/{sid}/states/{index}",
            data=SVG,
            content_type="image/svg+xml",
        )
        assert response.status_code == 200
    return sid


@pytest.fixture
def library_root(isolated_library):
    return isolated_library.root


@pytest.fixture
def installed_layer(client, complete_session, tmp_path, monkeypatch):
    result = client.post(f"/api/tessellations/sessions/{complete_session}/finalize")
    assert result.status_code == 200
    pfm_id = result.get_json()["pattern"]["id"]

    monkeypatch.setattr(project_mod, "PROJECTS_DIR", tmp_path / "projects")
    project = project_mod.create_project("Tessellation resilience")
    image_buffer = io.BytesIO()
    Image.new("RGB", (12, 12), "gray").save(image_buffer, format="PNG")
    project.set_image(image_buffer.getvalue(), "source.png")
    monkeypatch.setattr(server, "_project", project)

    cached_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        'viewBox="0 0 10 10"><path d="M1 1 L9 9"/></svg>'
    )
    layer = project.composition.add_layer(
        cached_svg,
        "Custom tessellation",
        "pathfinding",
        {"pfm_id": pfm_id, "params": {}},
    )
    layer.pathfinding_style = {
        "enabled": True,
        "pfm_id": pfm_id,
        "params": {},
        "status": "clean",
        "error": "",
    }
    project.save_composition_layers()
    return layer


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


def test_installed_pattern_is_discoverable_and_generates(client, complete_session):
    result = client.post(f"/api/tessellations/sessions/{complete_session}/finalize")
    assert result.status_code == 200
    pfm_id = result.get_json()["pattern"]["id"]

    listed = client.get("/api/pfm/list").get_json()["pfms"]
    assert any(
        item["id"] == pfm_id and item["family"] == "tessellation"
        for item in listed
    )
    schema = client.get(f"/api/pfm/{pfm_id}/schema").get_json()
    assert any(param["name"] == "tone_response" for param in schema["params"])

    preview = client.get(f"/static/pfm-previews/{pfm_id}.png")
    assert preview.status_code == 200
    assert preview.mimetype == "image/png"

    items = generate_items(
        get_pfm(pfm_id), Image.new("RGB", (24, 24), "gray"), {}, 0, (24, 24)
    )
    assert any(item.path is not None for item in items)


def test_missing_package_does_not_remove_cached_layer_svg(
    client, installed_layer, library_root
):
    cached = installed_layer.svg
    pfm_id = installed_layer.source["pfm_id"]
    shutil.rmtree(library_root / pfm_id)
    REGISTRY.pop(pfm_id)

    response = client.post(
        f"/api/composition/layers/{installed_layer.id}/pathfinding/generate",
        json={"pfm_id": pfm_id, "params": {}},
    )

    assert response.status_code == 400
    assert installed_layer.svg == cached
    assert installed_layer.pathfinding_style["status"] == "error"
    assert installed_layer.pathfinding_style["error"] == "Unknown PFM"
    payload = response.get_json()
    assert payload["composition"]["selected_layer_id"] == installed_layer.id

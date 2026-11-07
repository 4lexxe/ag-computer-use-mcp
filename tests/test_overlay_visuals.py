from windows_computer_use import overlay_visuals as visuals
from windows_computer_use import session_state


def test_true_transparency_thickness_and_edge_only_rendering():
    image = visuals.border_image(1280, 720)
    assert image.getpixel((640, 360))[3] == 0
    assert 0 < image.getpixel((640, 6))[3] < 160
    assert image.getpixel((640, 60))[3] > 0
    assert image.getpixel((0, 0))[3] > 0
    assert image.getpixel((640, 719))[3] > 0
    assert visuals.BORDER_WIDTH == 68
    peak = visuals.border_image(1280, 720, pulse=1.0)
    assert peak.getpixel((640, 90))[3] > image.getpixel((640, 90))[3]
    assert peak.getpixel((640, 360))[3] == 0
    assert visuals.EDGE_WIDTH >= visuals.BORDER_WIDTH + visuals.PULSE_GROWTH + 27
    boxes = visuals.edge_boxes(1920, 1080)
    assert (
        sum((right - left) * (bottom - top) for left, top, right, bottom in boxes)
        < 1920 * 1080 * 0.40
    )


def test_point_animation_changes_and_recycles_without_drawing_in_the_center():
    animation = visuals.EdgeAnimation(1280, 720, seed=10)
    first = animation.frames(100)
    second = animation.frames(100.6)
    assert any(a.tobytes() != b.tobytes() for a, b in zip(first, second))
    original = list(animation.points)
    animation.frames(110)
    assert len(animation.points) == visuals.PARTICLE_COUNT
    assert visuals.PARTICLE_COUNT >= 120
    assert all(new is not old for new, old in zip(animation.points, original))
    assert all(p.born == 110 for p in animation.points)


def test_official_svg_assets_are_packaged_and_renderable():
    for name in ("antigravity", "gemini"):
        image = visuals.brand_image(name, 32)
        assert image.size == (32, 32)
        assert image.mode == "RGBA"
        assert image.getbbox() is not None


def test_spanish_activity_does_not_replace_requested_english_headline():
    assert visuals.HEADLINE == "Antigravity is using your computer"
    assert (
        visuals.subtitle({"activity": "reading", "project_name": "Proyecto A"})
        == "Leyendo la pantalla · Proyecto A"
    )
    assert visuals.subtitle({"activity": "inspecting"}) == "Leyendo controles de la ventana"


def test_activity_updates_preserve_project_and_cannot_resume_cancelled_session(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(session_state, "STATUS_FILE", tmp_path / "state.json")
    session_state.write_status("active", "Proyecto A", activity="ready")
    session_state.set_activity("reading")
    assert session_state.read_status()["project_name"] == "Proyecto A"
    assert session_state.read_status()["activity"] == "reading"
    session_state.write_status("cancelled")
    session_state.set_activity("interacting")
    assert session_state.read_status() == {"status": "cancelled"}


def test_cursor_halo_trail_and_click_pulse_are_translucent():
    cursor = visuals.CursorAnimation()
    first = cursor.frame(100, 100, 10)
    second = cursor.frame(118, 107, 10.1, pressed=True)
    assert first.size == second.size == (112, 112)
    assert first.getpixel((0, 0))[3] == 0
    assert first.tobytes() != second.tobytes()
    # The badge contains original SVG pixels; the halo itself remains translucent.
    assert second.getpixel((cursor.center + 12, cursor.center))[3] < 255
    cursor.frame(200, 200, 11)
    assert len(cursor.history) == 1


def test_topmost_refresh_preserves_position_and_does_not_activate(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    from unittest.mock import Mock

    from windows_computer_use.layered_window import keep_topmost

    position = Mock(return_value=True)
    monkeypatch.setattr(ctypes.windll, "user32", SimpleNamespace(SetWindowPos=position))
    keep_topmost([101, 102])
    assert [call.args[0] for call in position.call_args_list] == [101, 102]
    for call in position.call_args_list:
        flags = call.args[-1]
        assert flags & 0x0010
        assert flags & 0x0001 and flags & 0x0002
        assert not flags & 0x0004

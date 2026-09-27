from app.ui_actions import build_messages, load_catalog, parse_action_response


def test_catalog_lists_every_action_table_row():
    _, catalog = load_catalog()
    for name in ("set_filters", "clear_filters", "set_layer", "select_track", "open_panel", "playback",
                 "set_theme", "set_voice_alerts", "ask_agent", "decide_review"):
        assert name in catalog


def test_parses_plain_json_plan():
    plan = parse_action_response('{"message": "Yalnızca otobüsler", "actions": ['
                                 '{"action": "clear_filters", "params": {}},'
                                 '{"action": "set_filters", "params": {"vehicle_class": "bus"}}]}')
    assert plan.message == "Yalnızca otobüsler"
    assert [(a.action, a.params) for a in plan.actions] == [("clear_filters", {}), ("set_filters", {"vehicle_class": "bus"})]


def test_strips_think_tags_and_code_fences():
    text = '<think>{"actions": [{"action": "bogus"}]}</think>Tamam:\n```json\n{"actions": [{"action": "set_theme", "params": {"mode": "light"}}]}\n```'
    plan = parse_action_response(text)
    assert [a.action for a in plan.actions] == ["set_theme"]


def test_drops_unknown_actions_and_accepts_flat_or_string_params():
    plan = parse_action_response('[{"name": "Set-Layer", "layer": "zones", "visible": false},'
                                 '{"function": {"name": "seek", "arguments": "{\\"time\\": \\"14:30\\"}"}},'
                                 '{"action": "delete_everything"}]')
    assert [(a.action, a.params) for a in plan.actions] == [
        ("set_layer", {"layer": "zones", "visible": False}), ("seek", {"time": "14:30"})]
    assert plan.dropped == ["delete_everything"]


def test_non_json_reply_becomes_message():
    plan = parse_action_response("Bunu arayüzde yapamam.")
    assert plan.actions == [] and plan.message == "Bunu arayüzde yapamam."


def test_messages_include_catalog_context_and_command():
    system, human = build_messages("Sadece otobüsleri göster", {"options": {"vehicle_class": ["bus", "car"]}})
    assert "set_filters" in system[1]
    assert '"vehicle_class":["bus","car"]' in human[1] and "Sadece otobüsleri göster" in human[1]

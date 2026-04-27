import autonomous_agent


def test_retired_autonomous_agent_exits_without_running_legacy_loop():
    assert autonomous_agent.run_agent() == autonomous_agent.EXIT_CODE_RETIRED

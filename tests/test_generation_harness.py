

class TestReasoningProvenance:
    """The system under test follows the config; the measuring instrument does not.

    C-07 varies `REASONING_EFFORT` to measure what extended reasoning does. Two
    things must be true for that measurement to mean anything: the baselines have
    to actually change when the switch moves, and the judge must not.
    """

    def test_the_harness_follows_the_config(self):
        import inspect

        from src.eval import generation_harness

        src = inspect.getsource(generation_harness.run_generation_eval)
        assert "reasoning_effort=cfg.REASONING_EFFORT" in src

    def test_reasoning_enabled_is_derived_not_asserted(self):
        """Written as a literal `False` this was a claim nobody checked — the
        same defect C-01 found in the citation harness."""
        import inspect

        from src.eval import generation_harness

        src = inspect.getsource(generation_harness.run_generation_eval)
        assert "reasoning_enabled=False" not in src
        assert 'reasoning_enabled=cfg.REASONING_EFFORT not in ("none", "", None)' in src

    def test_the_judge_is_pinned_and_does_not_read_the_config(self):
        """An instrument that changes with its subject cannot attribute the
        difference to either. And at max_tokens=16 a reasoning judge returns an
        empty verdict, which falls through to "wrong" — every judgement would
        quietly become a failure."""
        import inspect

        from src.generation import judge

        # Comments are stripped first: the one on that argument names
        # cfg.REASONING_EFFORT precisely to say it is not used, and a check on
        # the raw source would fail on its own explanation.
        code = "\n".join(line.split("#")[0]
                         for line in inspect.getsource(judge.judge_answer).splitlines())
        assert 'reasoning_effort="none"' in code
        assert "cfg.REASONING_EFFORT" not in code

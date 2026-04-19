import unittest
from unittest.mock import patch

from modules.module2 import sandbox


class FakeModelClient:
    def __init__(self, *, seller_drafts=None, seller_reviews=None, buyer_drafts=None, buyer_reviews=None):
        self._seller_drafts = list(seller_drafts or [])
        self._seller_reviews = list(seller_reviews or [])
        self._buyer_drafts = list(buyer_drafts or [])
        self._buyer_reviews = list(buyer_reviews or [])

    def generate_seller_line(self, analysis, simulation_state):
        return self._seller_drafts.pop(0)

    def evaluate_seller_draft(self, analysis, simulation_state, draft_response):
        return self._seller_reviews.pop(0)

    def generate_buyer_line(self, analysis, simulation_state):
        return self._buyer_drafts.pop(0)

    def evaluate_buyer_draft(self, analysis, simulation_state, draft_response):
        return self._buyer_reviews.pop(0)

    def mentor_analyze_demo_turn(self, **kwargs):
        return "Mentor note"


class CheckStoppingConditionTests(unittest.TestCase):
    def test_returns_agreement_when_key_terms_are_agreed(self):
        state = {
            "agreed_points": [
                "We agree on final price at 100.",
                "We agree on payment terms at 45 days.",
                "We agree on delivery timeline in 2 weeks.",
            ],
            "session_meta": {"deadlock_counter": 0, "turn_number": 6, "max_turns": 20},
            "history": [{"final_output": "discussion"} for _ in range(6)],
        }
        out = sandbox._check_stopping_condition(state)
        self.assertEqual(out["status"], "AGREEMENT")

    def test_returns_deadlock_when_counter_reaches_threshold(self):
        state = {
            "agreed_points": [],
            "session_meta": {"deadlock_counter": 3, "turn_number": 4, "max_turns": 20},
            "history": [],
        }
        out = sandbox._check_stopping_condition(state)
        self.assertEqual(out["status"], "DEADLOCK")

    def test_returns_terminated_when_withdrawal_detected(self):
        state = {
            "agreed_points": [],
            "session_meta": {"deadlock_counter": 0, "turn_number": 4, "max_turns": 20},
            "history": [{"final_output": "We will walk away from this negotiation."}],
        }
        out = sandbox._check_stopping_condition(state)
        self.assertEqual(out["status"], "TERMINATED")

    def test_returns_timeout_when_turn_limit_is_reached(self):
        state = {
            "agreed_points": [],
            "session_meta": {"deadlock_counter": 0, "turn_number": 20, "max_turns": 20},
            "history": [],
        }
        out = sandbox._check_stopping_condition(state)
        self.assertEqual(out["status"], "TIMEOUT")

    def test_returns_ongoing_when_no_condition_matches(self):
        state = {
            "agreed_points": [],
            "session_meta": {"deadlock_counter": 0, "turn_number": 2, "max_turns": 20},
            "history": [{"final_output": "We should continue discussing the terms."}],
        }
        out = sandbox._check_stopping_condition(state)
        self.assertEqual(out["status"], "ongoing")

    def test_simple_mode_deadlock_threshold_is_less_strict(self):
        state = {
            "agreed_points": [],
            "session_meta": {"difficulty": "simple", "deadlock_counter": 3, "turn_number": 8, "max_turns": 20},
            "history": [{"final_output": "Still discussing."}],
        }
        out = sandbox._check_stopping_condition(state)
        self.assertEqual(out["status"], "ongoing")


class CoachingLoopRegressionTests(unittest.TestCase):
    def setUp(self):
        self.analysis = {"summary": "demo", "key_points": [], "negotiation_points": []}

    def test_seller_loop_retries_then_passes_and_sets_buyer_adjustment(self):
        state = sandbox.init_simulation_state(self.analysis)
        fake = FakeModelClient(
            seller_drafts=["seller draft 1", "seller final"],
            seller_reviews=[
                {
                    "verdict": "FAIL",
                    "violations": ["R4"],
                    "recommendation": "Add a specific term.",
                    "deadlock_risk": "LOW",
                    "adjustment_for_next_turn": "Probe buyer decision criteria.",
                },
                {
                    "verdict": "PASS",
                    "violations": [],
                    "recommendation": "Good structure.",
                    "deadlock_risk": "LOW",
                    "adjustment_for_next_turn": "Ask for buyer commitment.",
                },
            ],
        )
        with patch("modules.module2.sandbox.get_model_client", return_value=fake):
            item = sandbox.simulate_seller_step(self.analysis, state)

        self.assertEqual(item["role"], "sales_ai")
        self.assertEqual(item["text"], "seller final")
        self.assertEqual(state["next_speaker"], "buyer")
        self.assertEqual(state["coaching_recs"]["for_buyer"], "Ask for buyer commitment.")
        self.assertEqual(state["history"][-1]["verdict"], "PASS")
        self.assertEqual(state["session_meta"]["turn_number"], 1)

    def test_buyer_loop_retries_then_passes_and_updates_seller_coaching(self):
        state = sandbox.init_simulation_state(self.analysis)
        state["next_speaker"] = "buyer"
        fake = FakeModelClient(
            buyer_drafts=["buyer draft 1", "buyer final"],
            buyer_reviews=[
                {
                    "verdict": "FAIL",
                    "violations": ["R6"],
                    "recommendation": "Ask a concrete clarification question.",
                    "deadlock_risk": "LOW",
                    "adjustment_for_next_turn": "Defend value with concrete examples.",
                },
                {
                    "verdict": "PASS",
                    "violations": [],
                    "recommendation": "Good challenge.",
                    "deadlock_risk": "HIGH",
                    "adjustment_for_next_turn": "Seller should request reciprocal commitment.",
                },
            ],
        )
        with patch("modules.module2.sandbox.get_model_client", return_value=fake):
            item = sandbox.simulate_buyer_step(self.analysis, state)

        self.assertEqual(item["role"], "buyer_ai")
        self.assertEqual(item["text"], "buyer final")
        self.assertEqual(state["next_speaker"], "seller")
        self.assertEqual(state["coaching_recs"]["for_seller"], "Seller should request reciprocal commitment.")
        self.assertEqual(state["history"][-1]["verdict"], "PASS")
        self.assertEqual(state["session_meta"]["deadlock_counter"], 1)

    def test_seller_loop_fails_three_times_and_uses_last_draft(self):
        state = sandbox.init_simulation_state(self.analysis)
        fake = FakeModelClient(
            seller_drafts=["seller draft 1", "seller draft 2", "seller draft 3"],
            seller_reviews=[
                {
                    "verdict": "FAIL",
                    "violations": ["R4"],
                    "recommendation": "Add concrete numbers.",
                    "deadlock_risk": "LOW",
                    "adjustment_for_next_turn": "Buyer should request specifics.",
                },
                {
                    "verdict": "FAIL",
                    "violations": ["R6"],
                    "recommendation": "Avoid repeating previous wording.",
                    "deadlock_risk": "LOW",
                    "adjustment_for_next_turn": "Buyer should pressure timeline.",
                },
                {
                    "verdict": "FAIL",
                    "violations": ["R10"],
                    "recommendation": "Add a more natural relational tone.",
                    "deadlock_risk": "MEDIUM",
                    "adjustment_for_next_turn": "Buyer should test commitment.",
                },
            ],
        )
        with patch("modules.module2.sandbox.get_model_client", return_value=fake):
            item = sandbox.simulate_seller_step(self.analysis, state)

        self.assertEqual(item["role"], "sales_ai")
        # On 3 consecutive FAILs, the system should still publish the last available draft.
        self.assertEqual(item["text"], "seller draft 3")
        self.assertEqual(state["history"][-1]["verdict"], "FAIL")
        self.assertEqual(state["history"][-1]["draft"], "seller draft 3")
        self.assertEqual(state["coaching_recs"]["for_seller"], "Add a more natural relational tone.")
        self.assertEqual(state["next_speaker"], "buyer")


if __name__ == "__main__":
    unittest.main()

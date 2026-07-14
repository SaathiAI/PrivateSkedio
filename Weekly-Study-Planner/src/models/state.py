"""Shared State Definitions for Study Planner Multi-Agent System.

This file previously held UserProfile, CanonicalItems, and a legacy
SupervisorState. Those models are now dead code:

- UserProfile / CanonicalItems were replaced by IntakeAgentOutput in intake.py
- SupervisorState is defined directly in supervisor_slop.py (the live supervisor)

Keeping this file as a thin module so any stale import paths still resolve
without crashing at import time.
"""

"""
parrhesia.touchstone
=====================
試金石(H章)サブパッケージ。生成AI個体の思考バイアスを、答えの分かって
いる問題群で機械的に測るための、問題生成(catalog)・採点(grader)・
実行(runner)。
"""
from parrhesia.touchstone.catalog import GENERATORS, generate_battery
from parrhesia.touchstone.grader import grade
from parrhesia.touchstone.runner import BatteryRunResult, run_battery
from parrhesia.touchstone.schema import GradeResult, Problem

__all__ = [
    "GENERATORS",
    "generate_battery",
    "grade",
    "BatteryRunResult",
    "run_battery",
    "GradeResult",
    "Problem",
]

import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv()
from google.genai import types as genai_types
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_case import EvalCase, SessionInput, Invocation
from google.adk.evaluation.eval_metrics import PrebuiltMetrics, EvalMetric, BaseCriterion, RubricsBasedCriterion
from google.adk.evaluation.eval_rubrics import Rubric, RubricContent
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet

async def run_manual_eval():
    os.environ["MOCK_MCP"] = "true"
    
    prompt = "I need to download the NVIDIA Fundamentals of Deep Learning certificate from my Coursera folder in Google Drive and move it to D:\\test."
    
    # Define Ground Truth (Expected Invocation)
    expected_invocation = Invocation(
        invocation_id="expected_01",
        user_content=genai_types.Content(parts=[genai_types.Part(text=prompt)]),
        final_response=genai_types.Content(parts=[genai_types.Part(text="The file NVIDIA Fundamentals of Deep Learning.pdf was successfully downloaded and moved to D:\\test.")])
    )
    
    session_input = SessionInput(
        app_name="agent",
        user_id="eval_user"
    )
    
    # Define Rubrics
    success_rubric = Rubric(
        rubric_id="task_success",
        rubric_content=RubricContent(
            text_property="The agent successfully downloads the NVIDIA Fundamentals of Deep Learning file from Google Drive and moves it to D:\\test."
        ),
        description="Evaluates if the final outcome of the RPA workflow is achieved.",
        type="FINAL_RESPONSE_QUALITY"
    )

    trajectory_rubric = Rubric(
        rubric_id="tool_usage_efficiency",
        rubric_content=RubricContent(
            text_property="The agent should use browser tools first, then authentication, then drive navigation, and finally filesystem tools."
        ),
        description="Evaluates the sequence and correctness of tool usage.",
        type="TOOL_USE_QUALITY"
    )

    # Use StaticConversation instead of Scenario to provide ground truth
    eval_case = EvalCase(
        eval_id="manual_test_01",
        conversation=[expected_invocation],
        session_input=session_input
    )
    
    # Define EvalSet
    eval_set = EvalSet(
        eval_set_id="manual_eval_set",
        name="Manual Eval Set",
        eval_cases=[eval_case]
    )
    
    # Define EvalConfig with Rubric-based metrics
    eval_config = EvalConfig(
        criteria={
            str(PrebuiltMetrics.RUBRIC_BASED_FINAL_RESPONSE_QUALITY_V1.value): RubricsBasedCriterion(
                threshold=0.8,
                rubrics=[success_rubric]
            ),
            str(PrebuiltMetrics.RUBRIC_BASED_TOOL_USE_QUALITY_V1.value): RubricsBasedCriterion(
                threshold=0.8,
                rubrics=[trajectory_rubric]
            )
        }
    )
    
    print("Starting evaluation via AgentEvaluator.evaluate_eval_set...")
    try:
        await AgentEvaluator.evaluate_eval_set(
            agent_module="agent",
            eval_set=eval_set,
            eval_config=eval_config,
            num_runs=1,
            print_detailed_results=True
        )
        print("\nEvaluation completed successfully.")
            
    except Exception as e:
        print(f"Evaluation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_manual_eval())

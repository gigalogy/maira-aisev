from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from src.constants.perspectives import TEN_PERSPECTIVES, to_japanese_perspective
from src.db.define_tables import EvaluationResult
from src.manager.evaluation_results_manager import EvaluationResultsManager
from src.db.session import get_db
from pydantic import BaseModel, model_validator
from typing import List, Literal, Optional, Any, Dict
from src.config import config as app_config
from src.utils.logger import logger
from src.enum import TargetModel, EvalModel, TargetLanguage
from src.helper import InvalidEvaluationConfiguration, validate_uuid

router = APIRouter()


class InlineAIModelConfig(BaseModel):
    name: TargetModel | EvalModel
    model_name: str
    url: Optional[str] = None
    api_key: Optional[str] = None
    api_request_format: Optional[Dict[str, Any]] = None
    
    @model_validator(mode="after")
    def set_defaults(self):
        # TARGET MODEL
        if self.name == TargetModel.maira:
            self.url = self.url or app_config.maira_api_url

        # EVALUATOR MODEL
        if self.name == EvalModel.openai:
            self.url = self.url or app_config.openai_api_url
            self.api_key = self.api_key or app_config.openai_api_key

        return self


class QualitativeResultItem(BaseModel):
    questionId: int
    answer: str
    text: str
    perspective: str
    scoreRate: float
    secondGoal: str
    gsnLeaf: str
    gsnName: str


class QualitativeResultRequest(BaseModel):
    evaluationId: int
    results: List[QualitativeResultItem]


class QuantitativeResultRequest(BaseModel):
    evaluationId: int
    results: Any


class EvaluationResultCreateRequest(BaseModel):
    name: str
    evaluation_id: int
    maira_project_id: Optional[str] = None
    maira_profile_id: Optional[str] = None
    target_ai_model_id: Optional[int] = None
    evaluator_ai_model_id: Optional[int] = None
    quantitative_eval_state: Optional[str] = None
    quantitative_results: Optional[Any] = None
    qualitative_results: Optional[Any] = None


# Add Pydantic models
class EvaluationResultResponse(BaseModel):
    id: int
    name: str
    created_date: str
    evaluation_name: str
    maira_project_id: Optional[str] = None
    maira_profile_id: Optional[str] = None
    target_ai_model_name: Optional[str] = None
    evaluator_ai_model_name: Optional[str] = None
    quantitative_results: Optional[Any] = None
    qualitative_results: Optional[Any] = None
    quantitative_eval_state: Optional[str] = "running"

    class Config:
        from_attributes = True


class QuantitativeRequest(BaseModel):
    evaluation_id: int
    maira_auth_token: Optional[str] = None
    target_ai_model_id: Optional[int] = None
    evaluator_ai_model_id: Optional[int] = None
    target_model: Optional[InlineAIModelConfig] = None
    evaluator_model: Optional[InlineAIModelConfig] = None


@router.get("/evaluation_results/", response_model=List[EvaluationResultResponse])
def get_all_evaluation_results(
    maira_project_id: Optional[str] = Query(None),
    maira_profile_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get all evaluation results
    """
    logger.info("get_all_evaluation_results: 全ての評価結果取得処理を開始します。")
    try:
        maira_project_id = validate_uuid(maira_project_id, "maira_project_id")
        maira_profile_id = validate_uuid(maira_profile_id, "maira_profile_id")
        evaluation_results = EvaluationResultsManager.get_all_evaluation_results(
            maira_project_id=maira_project_id,
            maira_profile_id=maira_profile_id,
            db=db,
        )
        # Convert to YYYY-MM-DD hh:mm:ss format from created_date
        for result in evaluation_results:
            result["created_date"] = result["created_date"].strftime(
                "%Y-%m-%d %H:%M:%S")
        logger.info(
            f"get_all_evaluation_results: {len(evaluation_results)}件の評価結果を取得しました。")
        return evaluation_results
    except Exception as e:
        logger.error(f"get_all_evaluation_results: 取得処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価結果一覧の取得中にエラーが発生しました。")


@router.post("/evaluation_result/", response_model=int)
def create_evaluation_result(request: EvaluationResultCreateRequest, db: Session = Depends(get_db)):
    """
    The following is normally empty
    quantitative_eval_state
    quantitative_results
    qualitative_results
    """
    logger.info(
        f"create_evaluation_result: 評価結果 '{request.name}' の作成処理を開始します。")
    eval_result = EvaluationResult(
        name=request.name,
        evaluation_id=request.evaluation_id,
        maira_project_id=request.maira_project_id,
        maira_profile_id=request.maira_profile_id,
        target_ai_model_id=request.target_ai_model_id,
        evaluator_ai_model_id=request.evaluator_ai_model_id,
        quantitative_eval_state="running",
        quantitative_results=request.quantitative_results,
        qualitative_results=request.qualitative_results
    )
    try:
        # NOTE: create a empty result
        result_id = EvaluationResultsManager.create_evaluation_result(
            db, eval_result)
        logger.info(
            f"create_evaluation_result: 評価結果(ID={result_id}) の作成が完了しました。")
        return result_id
    except Exception as e:
        logger.error(f"create_evaluation_result: 作成処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価結果の作成中にエラーが発生しました。")


@router.post("/evaluation_results/{eval_result_id}/quantitative_result", response_model=int)
def exec_quantitative_evaluation(
    eval_result_id: int,
    request: QuantitativeRequest,
    db: Session = Depends(get_db)
):
    """
    request must contain either:
        - evaluation_id, target_ai_model_id, evaluator_ai_model_id (IDs)
        - evaluation_id, target_model, evaluator_model (inline configs)
    """
    logger.info(
        f"exec_quantitative_evaluation: ID={eval_result_id} の定量評価処理を開始します。")
    try:
        dataset_ids = EvaluationResultsManager.get_dataset_ids_from_evaluation_id(
            db, request.evaluation_id)

        # Search for UseGSN by evaluation_id
        use_gsn = EvaluationResultsManager.get_gsn_by_evaluation_id(
            db, request.evaluation_id)
        logger.info(f"exec_quantitative_evaluation: UseGSN={use_gsn}")
        if not dataset_ids and not use_gsn:
            logger.info("exec_quantitative_evaluation: データセットが見つかりませんでした。")
            raise HTTPException(
                status_code=404, detail="No datasets found for the evaluation")
        
        evaluation_result = db.query(EvaluationResult).filter(
            EvaluationResult.id == eval_result_id
        ).first()

        if evaluation_result is None:
            raise HTTPException(status_code=404, detail=f"EvaluationResult {eval_result_id} not found")

        # NOTE: Execute quantitative evaluation in background and return result_id when complete
        result_id = EvaluationResultsManager.register_quantitative_result(
            db, 
            eval_result_id, 
            dataset_ids, 
            request.target_ai_model_id, 
            request.evaluator_ai_model_id, 
            use_gsn,
            evaluation_result.maira_project_id,
            request.maira_auth_token,
            target_model_config=request.target_model.model_dump(mode="json") if request.target_model else None,
            eval_model_config=request.evaluator_model.model_dump(mode="json") if request.evaluator_model else None,
        )

        logger.info(
            f"exec_quantitative_evaluation: 定量評価(ID={result_id}) の登録が完了しました。")
        return result_id
    except InvalidEvaluationConfiguration as e:
        logger.error(f"exec_quantitative_evaluation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        logger.error(
            "exec_quantitative_evaluation: 評価用データセットまたはモデルが見つかりませんでした。")
        raise HTTPException(
            status_code=404, detail="No datasets found for the evaluation")
    except Exception as e:
        logger.error(f"exec_quantitative_evaluation: 定量評価処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="定量評価の登録中にエラーが発生しました。")


@router.post("/evaluation_results/{eval_result_id}/qualitative_result", response_model=int)
def register_qualitative_result(eval_result_id: int, qualitative_result: QualitativeResultRequest, db: Session = Depends(get_db)):
    logger.info(
        f"register_qualitative_result: ID={eval_result_id} の定性評価結果登録処理を開始します。")
    try:
        result_id = EvaluationResultsManager.register_qualitative_result(
            db, eval_result_id, qualitative_result.model_dump())
        logger.info(
            f"register_qualitative_result: 定性評価結果(ID={result_id}) の登録が完了しました。")
        return result_id
    except ValueError:
        logger.error("register_qualitative_result: EvaluationResultが見つかりません。")
        raise HTTPException(
            status_code=404, detail="EvaluationResult not found")
    except Exception as e:
        logger.error(f"register_qualitative_result: 登録処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="定性評価結果の登録中にエラーが発生しました。")


@router.get("/evaluation_results/{eval_result_id}/status", response_model=str)
def get_eval_status(eval_result_id: int, db: Session = Depends(get_db)):
    logger.info(f"get_eval_status: ID={eval_result_id} のステータス取得処理を開始します。")
    try:
        status = EvaluationResultsManager.get_eval_status(db, eval_result_id)
        if status is None:
            logger.info("get_eval_status: EvaluationResultが見つかりません。")
            raise HTTPException(
                status_code=404, detail="EvaluationResult not found")
        logger.info(f"get_eval_status: ステータスは '{status}' です。")
        return status
    except ValueError:
        logger.error("get_eval_status: EvaluationResultが見つかりません。")
        raise HTTPException(
            status_code=404, detail="EvaluationResult not found")
    except Exception as e:
        logger.error(f"get_eval_status: ステータス取得処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="ステータス取得中にエラーが発生しました。")


@router.get("/evaluation_results/{eval_result_id}/10perspective_scores", response_model=dict)
def get_10perspective_scores(eval_result_id: int, db: Session = Depends(get_db)):
    """
    Get 10-perspective scores
    """
    logger.info(
        f"get_10perspective_scores: ID={eval_result_id} の10観点スコア取得処理を開始します。")
    try:
        scores = EvaluationResultsManager.calculate_10perspective_scores(
            db, eval_result_id)
        logger.info("get_10perspective_scores: 10観点スコアの取得が完了しました。")
        return scores
    except ValueError:
        logger.error("get_10perspective_scores: EvaluationResultが見つかりません。")
        raise HTTPException(
            status_code=404, detail="EvaluationResult not found")
    except Exception as e:
        logger.error(f"get_10perspective_scores: 取得処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="10観点スコアの取得中にエラーが発生しました。")


@router.get("/evaluation_results/{eval_result_id}/detail", response_model=Any)
def get_evaluation_result_detail(
    eval_result_id: int,
    score_filter: Optional[Literal["0", "1"]] = None,
    target_language: TargetLanguage = TargetLanguage.japanese,
    db: Session = Depends(get_db)
):
    """
    Get detailed information for the specified evaluation result ID and return quantitative_results and qualitative_results in a readable format
    """
    logger.info(
        f"get_evaluation_result_detail: ID={eval_result_id} の詳細取得処理を開始します。")
    if score_filter is not None:
        score_filter = int(score_filter)
    try:
        detail = EvaluationResultsManager.get_result_detail(db, eval_result_id, score_filter=score_filter, target_language=target_language)
        logger.info("get_evaluation_result_detail: 詳細取得が完了しました。")
        return detail
    except ValueError:
        logger.exception(
            "get_evaluation_result_detail: EvaluationResultが見つかりません。")
        raise HTTPException(
            status_code=404, detail="EvaluationResult not found")
    except Exception as e:
        logger.exception(
            f"get_evaluation_result_detail: 詳細取得処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価結果詳細の取得中にエラーが発生しました。")


@router.get(
    "/evaluation_results/{eval_result_id}/combined_detail", response_model=Dict[str, Any],
)
def get_combined_evaluation_detail(
    eval_result_id: int,
    score_filter: Optional[Literal["0", "1"]] = None,
    target_language: TargetLanguage = TargetLanguage.japanese,
    download: Optional[bool] = Query(False, description="Download as JSON file"),
    db: Session = Depends(get_db),
):
    """
    Get combined detailed information for the specified evaluation result ID,
    including both quantitative and qualitative results, and return in a readable format.
    If 'download' is true, return as a downloadable JSON file.
    """
    logger.info(
        f"get_combined_evaluation_detail: ID={eval_result_id} の統合詳細取得処理を開始します。"
    )

    if score_filter is not None:
        score_filter = int(score_filter)

    try:
        # Get basic evaluation result info
        eval_result = db.query(EvaluationResult).filter_by(id=eval_result_id).first()
        if eval_result is None:
            logger.error(
                "get_combined_evaluation_detail: EvaluationResultが見つかりません。"
            )
            raise HTTPException(status_code=404, detail="EvaluationResult not found")

        # Get detailed results
        detail_results = EvaluationResultsManager.get_result_detail(
            db,
            eval_result_id,
            score_filter=score_filter,
            target_language=target_language,
        )

        # Get 10-perspective scores
        perspective_scores = EvaluationResultsManager.calculate_10perspective_scores(
            db, eval_result_id
        )

        # Build the combined response
        combined_response = {
            "evaluationResultName": eval_result.name,
            "evaluationName": (
                eval_result.evaluation.name if eval_result.evaluation else None
            ),
            "evaluatedDate": (
                eval_result.created_date.strftime("%Y-%m-%d %H:%M:%S")
                if eval_result.created_date
                else None
            ),
            "tenPerspectives": [],
        }

        normalized_detail_results = {}

        for perspective_name, results in detail_results.items():
            ja_name = to_japanese_perspective(perspective_name)
            normalized_detail_results[ja_name] = results

        # Convert detail results to the requested format
        for item in TEN_PERSPECTIVES:
            ja_name = item["ja"]
            en_name = item["en"]

            # Output language
            perspective_name = (
                ja_name if target_language == TargetLanguage.japanese else en_name
            )

            perspective_score = perspective_scores.get(ja_name, 0)

            results = normalized_detail_results.get(ja_name, [])

            perspective_data = {
                "perspective": perspective_name,
                "totalScore": perspective_score,
                "results": [],
            }

            for result in results:
                result_data = {
                    "subCategory": result.get("secondGoal", [""])[0],
                    "evaluationContent": result.get("gsnLeaf", [""])[0],
                    "scoreRate": result.get("scoreRate", [0])[0],
                    "category": result.get("type", "Quantitative"),
                    "question": result.get("question", ""),
                    "answer": result.get("answer", ""),
                    "score": result.get("score", 0),
                }

                perspective_data["results"].append(result_data)

            combined_response["tenPerspectives"].append(perspective_data)

        logger.info("get_combined_evaluation_detail: 統合詳細取得が完了しました。")

        # Return as downloadable JSON if requested
        if download:
            return JSONResponse(
                content=combined_response,
                headers={
                    "Content-Disposition": f"attachment; filename=evaluation_result_{eval_result_id}_detail.json"
                },
            )

        return combined_response

    except ValueError:
        logger.exception(
            "get_combined_evaluation_detail: EvaluationResultが見つかりません。"
        )
        raise HTTPException(status_code=404, detail="EvaluationResult not found")
    except Exception as e:
        logger.exception(
            f"get_combined_evaluation_detail: 統合詳細取得処理中にエラーが発生しました: {e}"
        )
        raise HTTPException(
            status_code=500, detail="評価結果統合詳細の取得中にエラーが発生しました。"
        )

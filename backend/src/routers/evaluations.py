from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from src.utils.gn_data import TOXIC_EVALUATION_JSON
from src.db.session import get_db
from src.manager.evaluation_manager import EvaluationManager
from src.utils.logger import logger

router = APIRouter()


@router.get("/evaluations")
def list_evaluations(db: Session = Depends(get_db)):
    logger.info("list_evaluations: 評価一覧取得処理を開始します。")
    try:
        evaluations = EvaluationManager(db).get_all()

        logger.info(f"list_evaluations: {len(evaluations)}件の評価を取得しました。")
        logger.warning(f"evaluations: {evaluations}")
        return {"evaluations": [
            {
                "id": e['id'],
                "name": e['name'],
                "createdAt": e['created_date'],
                "usedDatasets": e['used_dataset_names']
            }
            for e in evaluations
        ]}
    except Exception as e:
        logger.error(f"list_evaluations: 取得処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価一覧の取得中にエラーが発生しました。")


@router.post("/evaluation")
async def create_evaluation(payload: Dict[str, Any] = TOXIC_EVALUATION_JSON, db: Session = Depends(get_db)):
    logger.info("create_evaluation: 評価作成リクエストの処理を開始します。")
    try:
        logger.info(f"create_evaluation: 受信データ: {payload}")
        evaluation = await EvaluationManager(db).register_evaluation_from_json(payload)
        logger.info(f"create_evaluation: 評価(ID={evaluation.id}) の作成が完了しました。")
        return {"evaluation_id": evaluation.id}
    except Exception as e:
        logger.error(f"create_evaluation: 作成処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価の作成中にエラーが発生しました。")


@router.delete("/evaluation/{evaluation_id}")
def delete_evaluation(evaluation_id: int, db: Session = Depends(get_db)):
    logger.info(f"delete_evaluation: ID={evaluation_id} の評価削除リクエストの処理を開始します。")
    try:
        result = EvaluationManager(db).delete_evaluation_by_id(evaluation_id)
        if not result:
            logger.info(
                f"delete_evaluation: ID={evaluation_id} の評価は見つかりませんでした。")
            raise HTTPException(status_code=404, detail="Evaluation not found")
        logger.info(f"delete_evaluation: ID={evaluation_id} の評価削除が完了しました。")
        return {"result": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_evaluation: 削除処理中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価の削除中にエラーが発生しました。")

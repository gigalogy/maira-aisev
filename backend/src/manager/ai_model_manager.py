from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.helper import enum_error
from src.db.define_tables import AIModel
from src.utils.logger import logger
from src.enum import AIModelName, AIModelType
from src.config import config as app_config

class AIModelManager:
    """
    A class that consolidates database operations related to AI models
    """

    @staticmethod
    def add_model(db: Session, data: dict):
        """
        Add an AI model
        :param db: SQLAlchemy Session
        :param data: dict (name, url, api_key, api_request_format, type)
        :return: AIModel
        """
        logger.info("add_model: AIモデル追加処理を開始します。")
        if "name" not in data:
            raise ValueError("name is required")

        data = AIModelManager.normalize_ai_model_data(data)
        try:
            model = AIModel(
                name=data["name"],
                model_name=data.get("model_name"),
                url=data.get("url"),
                maira_project_key=data.get("maira_project_key"),
                maira_api_key=data.get("maira_api_key"),
                api_key=data.get("api_key"),
                api_request_format=data.get("api_request_format"),
                type=data["type"],
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            logger.info(f"add_model: AIモデル {model.name} の追加が完了しました。")
            return model
        except Exception as e:
            logger.error(f"add_model: 追加処理中にエラーが発生しました: {e}")
            db.rollback()
            raise

    @staticmethod
    def get_model_by_id(db: Session, model_id: int):
        """
        Get an AI model by ID
        :param db: SQLAlchemy Session
        :param model_id: int
        :return: AIModel or None
        """
        logger.info(f"get_model_by_id: ID={model_id} のAIモデル取得を開始します。")
        try:
            model = db.query(AIModel).filter(AIModel.id == model_id).first()
            if model:
                logger.info(f"get_model_by_id: AIモデル {model.name} を取得しました。")
            else:
                logger.info(f"get_model_by_id: ID={model_id} のAIモデルは見つかりませんでした。")
            return model
        except Exception as e:
            logger.error(f"get_model_by_id: 取得処理中にエラーが発生しました: {e}")
            return None

    @staticmethod
    def get_all_models(
        db: Session,
        maira_project_key: Optional[str] = None,
        maira_api_key: Optional[str] = None,
        gpt_profile_id: Optional[str] = None,
    ) -> List[AIModel]:
        """
        Get all AI models
        - If no filters are provided → return all models
        - If filters are provided → apply them conditionally
        """
        logger.info(
            "get_all_models: maira_project_key=%s, maira_api_key=%s, gpt_profile_id=%s",
            maira_project_key,
            maira_api_key,
            gpt_profile_id,
        )

        try:
            query = db.query(AIModel)

            # Apply filters only if provided
            if maira_api_key:
                query = query.filter(AIModel.maira_api_key == maira_api_key)

            if maira_project_key:
                query = query.filter(AIModel.maira_project_key == maira_project_key)
            if gpt_profile_id:
                query = query.filter(
                    func.json_extract_path_text(
                        AIModel.api_request_format,
                        "gpt_profile_id",
                    )
                    == gpt_profile_id
                )

            models = query.all()
            logger.info(f"get_all_models: {len(models)}件のAIモデルを取得しました。")
            return models
        except Exception as e:
            logger.error(f"get_all_models: 取得処理中にエラーが発生しました: {e}")
            return []

    @staticmethod
    def update_model(db: Session, model_id: int, data: dict):
        """
        Update an AI model
        :param db: SQLAlchemy Session
        :param model_id: int
        :param data: dict
        :return: AIModel or None
        """
        logger.info(f"update_model: ID={model_id} のAIモデル更新を開始します。")
        try:
            model = db.query(AIModel).filter(AIModel.id == model_id).first()
            if not model:
                logger.info(f"update_model: ID={model_id} のAIモデルは見つかりませんでした。")
                return None

            # Strip forbidden fields early
            FORBIDDEN_FIELDS = {"type", "api_key", "url"}
            data = {k: v for k, v in data.items() if k not in FORBIDDEN_FIELDS}

            # Recompute rules if name changes
            if "name" in data:
                base = {
                    c.name: getattr(model, c.name)
                    for c in model.__table__.columns
                }
                data = AIModelManager.normalize_ai_model_data({**base, **data})

            # Apply normal fields
            for key, value in data.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            db.commit()
            db.refresh(model)
            logger.info(f"update_model: AIモデル {model.name} の更新が完了しました。")
            return model
        except Exception as e:
            logger.error(f"update_model: 更新処理中にエラーが発生しました: {e}")
            db.rollback()
            return None

    @staticmethod
    def delete_model(db: Session, model_id: int):
        """
        Delete an AI model
        :param db: SQLAlchemy Session
        :param model_id: int
        :return: bool
        """
        logger.info(f"delete_model: ID={model_id} のAIモデル削除を開始します。")
        try:
            model = db.query(AIModel).filter(AIModel.id == model_id).first()
            if not model:
                logger.info(f"delete_model: ID={model_id} のAIモデルは見つかりませんでした。")
                return False
            db.delete(model)
            db.commit()
            logger.info(f"delete_model: AIモデル {model.name} の削除が完了しました。")
            return True
        except Exception as e:
            logger.error(f"delete_model: 削除処理中にエラーが発生しました: {e}")
            db.rollback()
            return False

    @staticmethod
    def normalize_ai_model_data(data: dict) -> dict:
        try:
            name = AIModelName(data["name"])
        except ValueError:
            raise enum_error(AIModelName, "name")

        if name == AIModelName.maira:
            return {
                **data,
                "type": AIModelType.target.value,
                "url": app_config.maira_api_url,
            }

        if name == AIModelName.openai:
            if not app_config.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured")

            return {
                **data,
                "type": AIModelType.eval.value,
                "api_key": None,
                "url": app_config.openai_api_url,
            }

        return {
            **data,
            "type": AIModelType.both.value,
        }

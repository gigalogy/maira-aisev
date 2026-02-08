from sqlalchemy.orm import Session
from src.db.define_tables import AIModel
from src.utils.logger import logger

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
        allowed_types = {"target", "eval", "both"}
        model_type = data.get("type")
        if model_type is None:
            model_type = "both"
        elif model_type not in allowed_types:
            logger.error(f"add_model: typeが不正です: {model_type}")
            raise ValueError("type must be one of: target, eval, both")
        try:
            model = AIModel(
                name=data.get("name"),
                model_name=data.get("model_name"),
                url=data.get("url"),
                api_key=data.get("api_key"),
                api_request_format=data.get("api_request_format"),
                type=model_type
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
    def get_all_models(db: Session):
        """
        Get all AI models
        :param db: SQLAlchemy Session
        :return: List[AIModel]
        """
        logger.info("get_all_models: すべてのAIモデル取得を開始します。")
        try:
            models = db.query(AIModel).all()
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

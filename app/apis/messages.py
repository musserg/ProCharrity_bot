from flask_restful import Resource
from flask_apispec.views import MethodResource
from flask import jsonify, make_response

from flask_apispec import doc, use_kwargs
from marshmallow import fields, Schema
from app.database import db_session
from app.models import Notification

from flask_jwt_extended import jwt_required, get_jwt_identity
from app import config
from bot.messages import TelegramNotification
import datetime


class TelegramNotificationSchema(Schema):
    message = fields.String(required=True)
    has_mailing = fields.String(required=True)


class SendTelegramNotification(Resource, MethodResource):

    @doc(description='Sends message to the Telegram chat. Requires "message" parameter.'
                     ' Messages can be sent either to subscribed users or not.To do this,'
                     ' specify the "has_mailing" parameter.Default value "True".',
         summary='Send messages to the bot chat',
         tags=['Messages'],
         responses={
             200: {'description': 'The message has been added to a query job'},
             400: {'description': 'The message can not be empty'},
         },
         params={
             'message': {
                 'description': 'Notification message. Max len 4096',
                 'in': 'query',
                 'type': 'string',
                 'required': True
             },
             'has_mailing': {
                 'description': ('Sending notifications to users by the type of permission to mailing.'
                                 'subscribed - user has enabled a mailing.'
                                 'unsubscribed - user has disabled a mailing.'
                                 'all - send to all users'),
                 'in': 'query',
                 'type': 'string',
                 'required': True
             },
             'Authorization': config.PARAM_HEADER_AUTH,  # Only if request requires authorization
         }
         )
    @use_kwargs(TelegramNotificationSchema)
    @jwt_required()
    def post(self, **kwargs):
        message = kwargs.get('message')
        has_mailing = kwargs.get('has_mailing')

        if not message or not has_mailing:
            return make_response(jsonify(result="Необходимо указать параметры <message> и <has_mailing>."), 400)

        # add a sending message to database
        authorized_user = get_jwt_identity()
        message = Notification(message=message, sent_by=authorized_user)
        db_session.add(message)
        db_session.commit()

        job_queue = TelegramNotification(has_mailing)

        if not job_queue.send_notification(message=message.message):
            return make_response(jsonify(result=f"Неверно указан параметр <has_mailing>. "
                                                f"Сообщение не отправлено."), 400)

        message.was_sent = True
        message.sent_date = datetime.datetime.now()
        db_session.commit()
        return make_response(jsonify(result=f"Сообщение успешно добавлено в очередь рассылки."), 200)

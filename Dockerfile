# for local testing

FROM amazon/aws-lambda-python:3.12
COPY src/requirements.txt /data/src/
RUN pip3 install -r /data/src/requirements.txt --target "${LAMBDA_TASK_ROOT}"
COPY src ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]
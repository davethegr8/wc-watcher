FROM python:3.6

WORKDIR /usr/src

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY . /usr/src

CMD ["python", "soccerbot.py"]
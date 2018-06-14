FROM python:3.6

ENV TZ=America/Los_Angeles

WORKDIR /usr/src

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY . /usr/src

CMD ["python", "soccerbot.py"]
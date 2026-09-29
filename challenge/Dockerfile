FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt
COPY . /srv/challenge
COPY entrypoint.sh /srv/entrypoint.sh
RUN sed -i 's/\r$//' /srv/entrypoint.sh
RUN chmod +x /srv/entrypoint.sh
ENV PYTHONPATH=/srv
EXPOSE 8080
CMD ["/srv/entrypoint.sh"]

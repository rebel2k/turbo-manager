FROM python:3.11
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
COPY  pages ./pages
COPY config ./config
COPY tools ./tools
COPY .streamlit ./.streamlit
EXPOSE 80
CMD [ "streamlit", "run","./Home.py" ]
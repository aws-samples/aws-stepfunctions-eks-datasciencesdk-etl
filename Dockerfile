FROM public.ecr.aws/ubuntu/ubuntu:20.04
COPY requirements.txt /tmp/requirements.txt
RUN apt update && apt install -y python3-pip
RUN python3 -m pip install jupyter==1.0.0 \
                            nbconvert==6.1.0 \
                            nbformat==5.1.3 \
                            ipython==7.25.0
RUN python3 -m pip install -r /tmp/requirements.txt
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
RUN mkdir -p /home/etlsample
COPY convert_execute_notebook.py /home/etlsample/convert_execute_notebook.py
COPY src/ /home/etlsample/src
ENV PYTHONPATH=/home/etlsample/src
WORKDIR /home/etlsample
ENTRYPOINT [ "python3", "convert_execute_notebook.py" ]

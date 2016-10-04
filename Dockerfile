FROM python:3.5.2

RUN apt-get update && \
        apt-get install -y build-essential &&  \
        rm -rf /var/lib/apt/lists/*

ENV LIBRDKAFKA_VERSION 0.9.1
RUN cd /tmp && \
        wget https://github.com/edenhill/librdkafka/archive/${LIBRDKAFKA_VERSION}.tar.gz && \
        tar -xzf ./${LIBRDKAFKA_VERSION}.tar.gz && \
        cd librdkafka-${LIBRDKAFKA_VERSION} && \
        ./configure && make && make install && make clean && ./configure --clean

ENV CPLUS_INCLUDE_PATH /usr/local/include
ENV LIBRARY_PATH /usr/local/lib
ENV LD_LIBRARY_PATH /usr/local/lib
ENV TERVIS_CONFIG /usr/src/app/dev-config.yml

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install -e .

CMD ["tervis"]

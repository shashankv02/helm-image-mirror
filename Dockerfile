FROM python:3 as builder
RUN wget https://download.docker.com/linux/static/stable/x86_64/docker-19.03.9.tgz \
    && tar -xvf docker-19.03.9.tgz \
    && wget https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 -O get_helm.sh \
    && chmod 700 ./get_helm.sh \
    && ./get_helm.sh

FROM python:3
WORKDIR /workdir
COPY --from=builder /docker/docker /usr/local/bin/docker
COPY --from=builder /usr/local/bin/helm /usr/local/bin/helm
RUN python3 -m pip install pyyaml

ADD src/ /usr/local/bin/
CMD ["helm_retag_images.py"]
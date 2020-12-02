FROM python:3

WORKDIR /workdir
Add helm_retag_images.py .
RUN python3 -m pip install pyyaml \
    && wget https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 -O get_helm.sh \
    && chmod 700 ./get_helm.sh \
    && ./get_helm.sh
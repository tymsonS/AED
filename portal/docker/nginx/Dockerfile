FROM nginx:1.31.6

ENV NGINX_ENVSUBST_TEMPLATE_DIR=/etc/nginx/templates
ENV NGINX_ENVSUBST_TEMPLATE_SUFFIX=.template
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/conf.d
COPY ./docker/nginx/config-templates ${NGINX_ENVSUBST_TEMPLATE_DIR}

ENV MCOD_CERTS_PATH=/etc/nginx/conf.d/certs
COPY ./docker/nginx/certs ${MCOD_CERTS_PATH}

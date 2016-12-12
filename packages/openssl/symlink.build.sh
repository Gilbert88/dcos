#!/bin/bash

mkdir -p ${PKG_PATH}/bin
mkdir -p ${PKG_PATH}/lib

ln -s /bin/openssl                          ${PKG_PATH}/bin/

ln -s /usr/lib64/.libcrypto.so.1.0.1e.hmac  ${PKG_PATH}/lib/
ln -s /usr/lib64/.libssl.so.1.0.1e.hmac     ${PKG_PATH}/lib/
ln -s /usr/lib64/libcom_err.so.2.1          ${PKG_PATH}/lib/
ln -s /usr/lib64/libcrypto.so.1.0.1e        ${PKG_PATH}/lib/
ln -s /usr/lib64/libgssapi_krb5.so.2.2      ${PKG_PATH}/lib/
ln -s /usr/lib64/libgssrpc.so.4.2           ${PKG_PATH}/lib/
ln -s /usr/lib64/libk5crypto.so.3.1         ${PKG_PATH}/lib/
ln -s /usr/lib64/libkadm5clnt_mit.so.8.0    ${PKG_PATH}/lib/
ln -s /usr/lib64/libkadm5srv_mit.so.9.0     ${PKG_PATH}/lib/
ln -s /usr/lib64/libkdb5.so.8.0             ${PKG_PATH}/lib/
ln -s /usr/lib64/libkrad.so.0.0             ${PKG_PATH}/lib/
ln -s /usr/lib64/libkrb5.so.3.3             ${PKG_PATH}/lib/
ln -s /usr/lib64/libkrb5support.so.0.1      ${PKG_PATH}/lib/
ln -s /usr/lib64/libssl.so.1.0.1e           ${PKG_PATH}/lib/

ln -s /usr/lib64/openssl/engines            ${PKG_PATH}/lib/engines
ln -s /usr/lib64/krb5/plugins               ${PKG_PATH}/lib/plugins


pushd ${PKG_PATH}/lib
ln -s .libcrypto.so.1.0.1e.hmac             .libcrypto.so.10.hmac
ln -s .libssl.so.1.0.1e.hmac                .libssl.so.10.hmac
ln -s libcom_err.so.2.1                     libcom_err.so.2
ln -s libcrypto.so.1.0.1e                   libcrypto.so.10
ln -s libgssapi_krb5.so.2.2                 libgssapi_krb5.so.2
ln -s libgssrpc.so.4.2                      libgssrpc.so.4
ln -s libk5crypto.so.3.1                    libk5crypto.so.3
ln -s libkadm5clnt_mit.so.8.0               libkadm5clnt_mit.so.8
ln -s libkadm5srv_mit.so.9.0                libkadm5srv_mit.so.9
ln -s libkdb5.so.8.0                        libkdb5.so.8
ln -s libkrad.so.0.0                        libkrad.so.0
ln -s libkrb5.so.3.3                        libkrb5.so.3
ln -s libkrb5support.so.0.1                 libkrb5support.so.0
ln -s libssl.so.1.0.1e                      libssl.so.10

ln -s libcom_err.so.2                       libcom_err.so
ln -s libcrypto.so.10                       libcrypto.so
ln -s libgssapi_krb5.so.2                   libgssapi_krb5.so
ln -s libgssrpc.so.4                        libgssrpc.so
ln -s libk5crypto.so.3                      libk5crypto.so
ln -s libkadm5clnt_mit.so.8                 libkadm5clnt_mit.so
ln -s libkadm5srv_mit.so.9                  libkadm5srv_mit.so
ln -s libkdb5.so.8                          libkdb5.so
ln -s libkrad.so.0                          libkrad.so
ln -s libkrb5.so.3                          libkrb5.so
ln -s libkrb5support.so.0                   libkrb5support.so
ln -s libssl.so.10                          libssl.so

popd

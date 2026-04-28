## Preparar o ambiente para levar os dados para o servidor.
    ## docker
    docker run -it --rm python:3.9 bash
    cd /home/
    mkdir rdsl
    cd rdsl
    echo "" > requirements.txt 
    ## nesse momento salva os pacores no arquivo pela interface do docker
    pip install --upgrade pip
    pip download -r requirements.txt -d /home/rdsl/packages

## Atualizando a versão no linux
    cd /appapi/rdsl_protocolo/
    pip install --no-index --find-links=packages -r requirements.txt

## Atualizando o serviço no linux
    #Criei um arquivo para configurar o serviço
        sudo nano /etc/systemd/system/rdsl_protocolo.service
    #Com o conteúdo 
        [Unit]
        Description=RDSL Protocolo API
        After=network.target
    
        [Service]
        User=root
        WorkingDirectory=/appapi/rdsl_protocolo
        Environment=PATH=/usr/local/bin:/usr/bin
        ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
        Restart=always
        
        [Install]
        WantedBy=multi-user.target
 
    #Reiniciei o controle de serviços e iniciei o serviço que criei 
        sudo systemctl daemon-reload
        sudo systemctl enable rdsl_protocolo
        sudo systemctl start rdsl_protocolo
        sudo systemctl stop rdsl_protocolo
        sudo systemctl restart rdsl_protocolo
 
    #Para analisar o log em tempo real basta usar o comando abaixo
        journalctl -u rdsl_protocolo -f
 

## Ambiente de interface
cd /appapi/gestao-protocolos-rd
nohup npm run dev > /dev/null 2>&1 &



#Para preparar o ambiente
pip install -r requirements.txt
pip download -r requirements.txt --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp --abi cp39 --only-binary=:all: -d packages
pip install --no-index --find-links=packages -r requirements.txt

#Para iniciar o projeto
python -m uvicorn app:app --reload
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000






# Cliente desktop Tauri

Wrapper Tauri v2 para abrir a interface local do Central ISO como aplicação desktop.

## Compilação

1. instale Rust e os pré-requisitos oficiais do Tauri 2;
2. inicie a API local em `http://127.0.0.1:8877`;
3. entre em `desktop/src-tauri`;
4. execute a build pelo Tauri CLI no ambiente Windows apropriado.

O repositório não versiona `target/`, executáveis, PDBs ou instaladores. Esses artefatos devem ser gerados pelo ambiente de build.

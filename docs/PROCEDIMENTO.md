# Procedimento técnico reproduzido no Redmi A5

Este é um procedimento de recuperação para técnicos, limitado ao perfil do README. A ferramenta Python prepara uma imagem **offline**; os comandos de gravação são manuais. Leia tudo antes de começar e mantenha o original disponível para restauração.

## 1. Confirmar o caso

O erro `set_policy_failed:/data/per_boot` sozinho não basta. É necessário confirmar no dump próprio de `rescue` que:

- O Recovery monta essa partição como `/cache`.
- `recovery/last_extension_parameters` contém exatamente `disable_factoryreset=1` seguido de quebra de linha.
- O log registra `config.disable_format=1` e/ou `WipeData disable_format is true`.
- Modelo, firmware e layout correspondem ao perfil testado; não há política de gerenciamento cuja remoção precise ser tratada com outro administrador.

Se o arquivo não existir, houver mais parâmetros ou o dump não corresponder ao perfil, não aplique esta receita. O programa deve recusar em vez de adivinhar.

## 2. Preparar o computador e as ferramentas

Obtenha Python 3.10 ou posterior, 7-Zip, Zadig do [site oficial](https://zadig.akeo.ie/), e `spd_dump`/loaders dos projetos originais referenciados no README. O programa offline foi executado em Python 3.15; usa somente biblioteca padrão.

O pacote de loaders utilizado foi o [UMS9230E Tecno KL4, release 1.72](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader/releases/tag/1.72), com `fdl1-dl.bin`, `fdl2-dl.bin` e `custom_exec_no_verify_65015f08.bin`. Apesar do nome Tecno, há relatos e estes dois testes de acesso no A5. Isso não prova compatibilidade com qualquer unidade ou firmware. O pacote UMS9230 genérico tem inicialização diferente e não deve ser substituído.

Não execute `unlock_autopatch_9230.bat`: esse fluxo modifica SPL/U-Boot para desbloqueio e apaga cópias de SPL em etapas intermediárias. A correção descrita aqui não precisa dessa sequência.

Use a versão **libusb/WinUSB** do `spd_dump` publicada pelo autor. Binários de terceiros não foram integralmente auditados por este projeto. O arquivo auxiliar deve existir, e seu caminho deve ser explícito em `loadexec`.

Tenha somente o aparelho alvo conectado. O BROM não apresentou o número de série Android na enumeração USB destes testes; selecionar o único alvo físico e depois conferir sua identidade no log foi essencial.

## 3. Driver WinUSB, sem alterar outro dispositivo

1. No próprio aparelho, abra o menu completo do Recovery e escolha **Power off**, se disponível. Nas duas unidades, a combinação dos dois volumes com Power permitiu alcançar o menu; o comportamento varia conforme a tela. Não confunda tela preta com confirmação de desligamento.
2. Com ele desligado, segure os dois volumes e conecte o USB, soltando após aproximadamente 2 segundos. A confirmação vem do PC: **USB VID `1782`, PID `4D00`**.
3. No Zadig, use **Device → Load Preset Device** e o `Redmi-A5-BROM.cfg` deste repositório. O preset permite preparar o driver mesmo com o celular desconectado. Confirme visualmente `1782 4D00`; não escolha Bluetooth, mouse, teclado ou dispositivo com outro ID.
4. Selecione **WinUSB** e instale. O kernel driver WinUSB é da Microsoft; o pacote específico criado pelo Zadig usa um catálogo gerado localmente, não uma certificação WHQL do fabricante do aparelho.
5. Confirme no Gerenciador de Dispositivos que a interface inicia sem erro. O driver antigo SPRD de 2015 apresentou código 52 nos testes; não desative assinatura obrigatória, Secure Boot ou antivírus. Se o Windows insistir no pacote antigo, identifique o INF exato antes de removê-lo. Não copie números `oemNNN.inf` de outra máquina.

Se um driver for associado ao dispositivo errado, pare e restaure o driver original desse dispositivo antes de continuar. O Bluetooth recebeu WinUSB por engano durante a execução manual inicial; ele foi restaurado ao driver MediaTek original e verificado com status normal. O preset foi acrescentado para evitar repetir essa seleção incorreta.

## 4. Conectar ao BROM e ler o próprio dump

Os caminhos abaixo são **exemplos**. Crie `C:\redmi-work\private` e coloque suas ferramentas em `C:\redmi-work\tools`. Ajuste os caminhos explicitamente. Não distribua `private/`.

Em PowerShell, inicie a espera **antes** de conectar o aparelho:

```powershell
& C:\redmi-work\tools\spd_dump.exe --wait 300 loadexec C:\redmi-work\tools\custom_exec_no_verify_65015f08.bin fdl C:\redmi-work\tools\fdl1-dl.bin 0x65000800 fdl C:\redmi-work\tools\fdl2-dl.bin 0x9efffe00 exec path C:\redmi-work\private r misc r rescue
```

Com somente o alvo desligado, conecte-o segurando os dois volumes. Aguarde o término das duas leituras e o prompt `FDL2 >`. Mantenha essa sessão aberta: o restante pode ser feito em outro terminal. Em automação, use um terminal que preserve stdin/PTY; uma sessão com stdin fechado não aceita comandos posteriores.

Nos testes apareceram avisos iniciais como `CHECK_BAUD FAIL`, `FDL2: incompatible partition` e uma resposta `0x00fe` para uma consulta de SPL. Não foram prova de sucesso nem motivo para ignorar falhas: só prosseguimos depois de os loaders responderem, a tabela ser lida, o layout ser conferido e cada leitura terminar com o tamanho esperado. Se houver timeouts contínuos, partição ausente ou tamanho incorreto, pare.

Confirme `rescue` com 134217728 bytes, preserve `misc` e gere hashes locais. Confira também a identidade do aparelho no `recovery/last_log` extraído; não publique esse identificador.

Alguns builds geram diretórios com data/hora e usam apenas o nome base de caminhos passados a `read_part`. Confira onde os arquivos foram realmente salvos. Nunca assuma que uma leitura foi concluída apenas porque um arquivo de tamanho pré-alocado existe.

## 5. Inspeção independente e alteração offline

Use 7-Zip para abrir o dump ext4 `rescue`, listar e extrair `recovery/last_extension_parameters` e os logs. Para seguir os exemplos abaixo, copie o dump original para `private/rescue-original.img`; mantenha outra cópia intocada fora da pasta de trabalho.

```powershell
python rescue_config.py inspect private/rescue-original.img
python rescue_config.py patch private/rescue-original.img --reference-file private/extracted/recovery/last_extension_parameters --output private/rescue-patched.img
```

A saída registra inode, offset e SHA-256. O programa resolve o caminho pelo filesystem e troca apenas o byte final do valor `1` por `0`; não muda tamanho, layout ou conteúdo de outros arquivos. Não há checksum de dados de arquivo a recalcular no perfil ext4 testado. Perfis com metadata checksums ou journal pendente são recusados.

Abra a imagem preparada com 7-Zip e confirme independentemente `disable_factoryreset=0`. A imagem é específica do aparelho que forneceu o dump; não use arquivos de outra unidade, mesmo do mesmo modelo.

## 6. Gravação manual e leitura integral de conferência

Esta etapa altera persistentemente o aparelho. Só a execute após conferir o arquivo de entrada, o alvo físico, os backups e a alteração de um byte. Não desconecte durante a gravação.

No **mesmo prompt `FDL2 >`**, execute uma linha por vez:

```text
w rescue C:\redmi-work\private\rescue-patched.img
read_part rescue 0 0x8000000 rescue-readback.img
```

Aguarde `Write Part Done` com 134217728 bytes escritos e `Read Part Done` com 134217728 bytes lidos. Localize o arquivo de leitura e, no outro terminal, compare:

```powershell
python rescue_config.py verify private/rescue-patched.img private/rescue-readback.img
```

Só prossiga com `verified: true`. Se não corresponder, **não reinicie normalmente**. Confirme a transferência e restaure a imagem original do **mesmo aparelho** na partição `rescue`, lendo-a de volta e comparando seu hash antes de sair. A subfunção `verify` exige a configuração corrigida, portanto, para restaurar o original, compare tamanho e SHA-256 diretamente com Python ou `Get-FileHash`. Não improvise gravações em outras partições se a conexão falhar; preserve os arquivos e procure recuperação especializada.

## 7. Recovery e restauração

Com leitura integral validada, no prompt FDL2:

```text
reboot-recovery
```

Esse comando escreve a solicitação de inicialização no BCB de `misc` e reinicia. No Recovery, escolha **Factory data reset** / **Wipe data/factory reset**, confirme e aguarde o sucesso. Depois use **Reboot system now**.

Nos dois testes o reset, que antes falhava, concluiu após a correção e o Android iniciou. A primeira configuração pode exigir a conta Google anteriormente vinculada e o reingresso no gerenciamento da organização. Este projeto não contorna essas proteções.

## Limites da intervenção

Não há instrução para apagar `persist`, `prodnv`, NV, calibração, bootloader ou tabela GPT; não são necessárias para esta correção. Não usamos imagens de outra região nem reinstalação de ROM como solução final. A causa da gravação original do parâmetro continua desconhecida.

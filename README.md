# CS2 Skin Monitor 🚀

Um monitor de skins para CS2 que realiza scraping em tempo real de múltiplos marketplaces (Buff163, CSFloat, CSMoney, DMarket, ShadowPay, etc.) para encontrar as melhores ofertas baseadas em preço e float.

## 🛠️ Como o Sistema Funciona

O sistema utiliza **Flet** para a interface gráfica e **Playwright** para automação de navegador. Ele se conecta a uma instância do Google Chrome rodando em modo de depuração remota (CDP) para contornar proteções anti-bot, permitindo a extração de dados de preços, floats e links diretos das ofertas.

### Principais Funcionalidades:
- **Monitoramento Simultâneo**: Busca em mais de 20 sites de skins.
- **Filtros Avançados**: Filtre por nome, estampa (skin), estilo (ex: Phase 1), range de float e preço.
- **Modo Stealth**: Utiliza o Chrome do usuário para evitar bloqueios.
- **Interface Moderna**: Visual Dark Mode com feedback em tempo real.

---

## 🚀 Como Rodar (Desenvolvimento)

### Pré-requisitos:
- Python 3.10 ou superior.
- Google Chrome instalado.

### Passo a Passo:

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/kaikyPx/skins.git
   cd skins
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   python -m venv venv
   # No Windows:
   .\venv\Scripts\activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Instale o Playwright (opcional, se usar browsers nativos):**
   ```bash
   playwright install chromium
   ```

5. **Execute o sistema:**
   ```bash
   python main.py
   ```

---

## 📂 Organização do Código

- `main.py`: Ponto de entrada da aplicação.
- `src/`: Pasta principal do código fonte.
  - `gui.py`: Contém toda a lógica da interface Flet e o loop principal de busca.
  - `scrapers/`: Contém os módulos individuais para cada site (ex: `buff.py`, `csfloat.py`).
  - `item.py`: Definição da classe `Item` que padroniza os dados coletados.
  - `utils.py`: Funções auxiliares.
- `CS2SkinMonitor.spec`: Configuração para compilação com PyInstaller.

---

## 📦 Como Compilar (Gerar Executável)

Para gerar o `.exe` único para Windows:

1. Instale o PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Execute o comando de build usando o arquivo `.spec` (recomendado):
   ```bash
   pyinstaller --clean --noconfirm CS2SkinMonitor.spec
   ```

O executável será gerado na pasta `dist/CS2SkinMonitor.exe`.

---

## ⚠️ Observações para Compilação
O arquivo `.spec` já está configurado para incluir os binários do `flet_desktop` e os drivers do `playwright`. Certifique-se de que o caminho da sua `venv` coincida com o definido no arquivo `.spec` ou ajuste-o conforme necessário.

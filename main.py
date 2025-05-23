import time, re
from flask import Flask, jsonify, request
from lxml import html
import undetected_chromedriver as uc
from seleniumbase import Driver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

def get_html_page(url):
    try:
        print("→ Запуск драйвера")
        driver = Driver(uc=True, headless=True)
        
        print("→ Открытие URL")
        driver.get(url)

        print("→ Ожидание элемента")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#stickyHeader"))
        )

        print("→ Скроллинг и ожидание")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(2)
        
        print("→ Получение HTML")
        html_content = driver.page_source
        driver.quit()
        return html_content

    except Exception as e:
        print(f"Ошибка при получении страницы: {str(e)}")
        raise

def parse_product_data(html_content, url):
    try:
        tree = html.fromstring(html_content)
        result = {'productLink': url}

        out_of_stock_xpath = "//h2[contains(text(), 'Товара нет в наличии') or contains(text(), 'Этот товар закончился')]"
        if tree.xpath(out_of_stock_xpath):
            return {
                'error': 'Товар закончился',
                'html': html_content[:500] + "...",
                'status': 422,
                "message": "Этот товар закончился"
            }

        title_xpath = "//div[@data-widget='webProductHeading']//h1/text()"
        title = tree.xpath(title_xpath)
        result['title'] = title[0].strip() if title else None

        ozon_price_xpath = "//div[@data-widget='webPrice']//span[contains(text(), '₽')]/text()"
        prices = tree.xpath(ozon_price_xpath)
        if prices:
            result['priceWithOzonCard'] = prices[0].strip()
            if len(prices) >= 2:
                result['price'] = prices[1].strip() 
            else:
                result['price'] = prices[0].strip()
        else:
            result['priceWithOzonCard'] = None
            result['price'] = None

        article_xpath = "//button[@data-widget='webDetailSKU']//div[contains(text(),'Артикул:')]/text()"
        article_text = tree.xpath(article_xpath)
        if article_text:
            match = re.search(r'\d+', article_text[0])
            result['article'] = match.group(0) if match else "Не найден"
        else:
            result['article'] = "Не найден"

        required_fields = ['title', 'price', 'article']
        missing_fields = [field for field in required_fields if not result.get(field)]

        if missing_fields:
            return {
                'error': f'Не удалось получить: {", ".join(missing_fields)}',
                'html': html_content[:500] + "...",
                'status': 422,
                "message": result
            }

        result['status'] = 200
        return result

    except Exception as e:
        print(f"Parsing error: {str(e)}")
        return {
            'error': str(e),
            'html': html_content[:500] + "...",
            'status': 500
        }


@app.route('/get_product', methods=['POST'])
def get_product():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'Missing required parameter: url'}), 400

        url = data['url']
        html_content = get_html_page(url)
        result = parse_product_data(html_content, url)

        return jsonify(result), result['status']

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)

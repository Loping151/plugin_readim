from PIL import Image
import pytesseract


def preprocess_image(image):
    image = image.convert("L")
    # image = image.point(lambda x: 0 if x < 128 else 255, '1') # 效果不好
    return image


def ocr_from_image(image, lang='eng+chi_sim'):
    image = preprocess_image(image)
    text1 = pytesseract.image_to_string(image, lang=lang)
    text2 = pytesseract.image_to_string(image, lang=lang, config = '--psm 6' )
    return text1+text2


# 测试代码
if __name__ == "__main__":
    img_path = "test.png"
    extracted_text = ocr_from_image(img_path)
    print(extracted_text)

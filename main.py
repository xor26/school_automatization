import json

from lxml import etree
from lxml.html import builder as html_builder
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait


class AchievementHelper:
    def __init__(self):
        self.result_exceptions = [
            "диплом",
            "аттестат",
            "лист",
            "сертификат",
            "дипломант",
            "благодарность",
            "грамота",
        ]

        self.new_result_map = {
            "участник": "Участие",
            "благодарность": "Благодарность",
            "призер": "Диплом",
            "призёр": "Диплом",
            "победитель": "Диплом",
        }

    def get_new_result(self, achievement_name):
        achievement_name = achievement_name.lower()
        for trigger_word in self.new_result_map:
            if trigger_word in achievement_name:
                return self.new_result_map[trigger_word]

        raise ValueError("Something wrong!")

    def is_result_exception(self, achievement_result):
        achievement_result = achievement_result.lower()
        for exc in self.result_exceptions:
            if exc in achievement_result:
                return True

        return False


class Logger:

    def __init__(self):
        self.log = {}

    def log_operation(self, profile_link, log_line):
        if profile_link not in self.log:
            self.log[profile_link] = []

        self.log[profile_link].append(log_line)

    def save_as_xml(self):
        root = etree.Element('data')
        for profile_id in self.log:
            profile_el = etree.SubElement(root, "profile")
            link = etree.SubElement(profile_el, "link")
            link.text = f"https://schools.dnevnik.ru/admin/persons/person.aspx?person={profile_id}&school=1172&view=achievements"
            for profile_ach in self.log[profile_id]:
                achiv_el = etree.SubElement(profile_el, "achievement")
                achiv_el.text = profile_ach

        tree = etree.ElementTree(root)
        tree.write("work_log.xml", pretty_print=True, xml_declaration=True, encoding="utf-8")


class SchoolHandler:
    def __init__(self, logger_instance):
        chrome_options = Options()
        chrome_options.add_argument("user-data-dir=selenium_data")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.logger = logger_instance

    def login_sequence(self, login, password):
        self.driver.get("https://login.dnevnik.ru/login")
        try:
            WebDriverWait(self.driver, 3).until(expected_conditions.presence_of_element_located(
                (By.XPATH, "/html/body/div/div/div/div/div/form/div[2]/div[3]/div[5]/div[2]/button"))).click()
        except TimeoutException as ex:
            print("First login")

        login_input = self.driver.find_element_by_name("login")
        login_input.send_keys(login)
        pass_input = self.driver.find_element_by_name("password")
        pass_input.send_keys(password)
        WebDriverWait(self.driver, 3).until(expected_conditions.presence_of_element_located(
            (By.CLASS_NAME, "login__submit"))).click()

    def get_profiles_from_page(self, page):
        self.driver.get("https://schools.dnevnik.ru/school.aspx?school=1172&view=members&group=students&page=" + page)
        profiles_ids = []
        for profiles_page_link_container in self.driver.find_elements_by_class_name("tdButtons"):
            try:
                profile_page_link = profiles_page_link_container. \
                    find_element_by_class_name("iE"). \
                    find_element_by_tag_name('a')
            except NoSuchElementException:
                continue

            profile_page_link = profile_page_link.get_attribute("href")
            profile_page_link = profile_page_link.split("=")[1]
            profile_page_link = profile_page_link.split("&")[0]
            profiles_ids.append(profile_page_link)

        return profiles_ids

    def get_total_profiles_pages(self):
        self.driver.get("https://schools.dnevnik.ru/school.aspx?school=1172&view=members&group=students")
        pager = self.driver.find_element_by_class_name("pager")
        last_page = pager.find_elements_by_tag_name("li")[-1]
        return last_page.text

    def go_to_achievements_page(self, profile_link):
        achievements_link = f"https://schools.dnevnik.ru/admin/persons/person.aspx?person={profile_link}&" \
                            f"school=1172&view=achievements"
        self.driver.get(achievements_link)

    def process_profile_bonuses(self, profile_link):
        for achievement in self.get_next_achievements():
            ach_name = achievement.find_elements_by_tag_name("td")[0].text
            ach_result = achievement.find_elements_by_tag_name("td")[1].text
            ach_helper = AchievementHelper()
            if ach_helper.is_result_exception(ach_result):
                log_line = f"Достижение '{ach_name}' не нуждается в редактировании"
                self.logger.log_operation(profile_link=profile_link, log_line=log_line)
                continue

            try:
                new_result = ach_helper.get_new_result(ach_name)
            except ValueError:
                log_line = f"Нет правил для достижения '{ach_name}', отмечено для ручной проверки"
                self.logger.log_operation(profile_link=profile_link, log_line=log_line)
                self.add_to_manual_check(profile_link, ach_name)
                continue

            self.update_result(achievement, new_result)
            log_line = f"Результат достижения '{ach_name}' будет заменен на '{new_result}'"
            self.logger.log_operation(profile_link=profile_link, log_line=log_line)

    def get_next_achievements(self):
        achievements_list = self.driver.find_element_by_id("mtabl") \
            .find_element_by_tag_name("tbody") \
            .find_elements_by_tag_name("tr")
        for achievement in achievements_list:
            yield achievement

    def is_current_page_has_achievements(self):
        try:
            self.driver.find_element_by_class_name("emptyData")
        except NoSuchElementException:
            return True
        return False

    def update_result(self, achievement, new_result):
        print(new_result)

    def add_to_manual_check(self, link, achievement_name):
        print("HANDWORK!")

    def quit(self):
        self.driver.quit()


if __name__ == '__main__':
    logger = Logger()
    school_handler = SchoolHandler(logger_instance=logger)

    with open('credentials') as json_file:
        credential_data = json.load(json_file)
        school_handler.login_sequence(credential_data["login"], credential_data["password"])

    profiles_pages = school_handler.get_total_profiles_pages()
    # for page in range(1, int(profiles_pages)):
    for page in range(1, 11):
        profiles_from_current_page = school_handler.get_profiles_from_page(str(page))
        for profile in profiles_from_current_page:
            school_handler.go_to_achievements_page(profile)
            if not school_handler.is_current_page_has_achievements():
                continue
            school_handler.process_profile_bonuses(profile)

    school_handler.quit()
    logger.save_as_xml()

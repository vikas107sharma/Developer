from abc import ABC, abstractmethod


# 1. Target interface expected by the client
class IReports(ABC):
    @abstractmethod
    def get_json_data(self, data: str) -> str:
        pass


# 2. Adaptee: provides XML data from a raw input
class XmlDataProvider:
    # Expect data in "name:id" format (e.g. "Alice:42")
    def get_xml_data(self, data: str) -> str:
        name, id_ = data.split(":")
        return f"<user><name>{name}</name><id>{id_}</id></user>"


# 3. Adapter: implements IReports by converting XML → JSON
class XmlDataProviderAdapter(IReports):
    def __init__(self, provider: XmlDataProvider):
        self.xml_provider = provider

    def get_json_data(self, data: str) -> str:
        # 1. Get XML from the adaptee
        xml = self.xml_provider.get_xml_data(data)

        # 2. Naïvely parse out <name> and <id> values
        start_name = xml.find("<name>") + len("<name>")
        end_name = xml.find("</name>")
        name = xml[start_name:end_name]

        start_id = xml.find("<id>") + len("<id>")
        end_id = xml.find("</id>")
        id_ = xml[start_id:end_id]

        # 3. Build and return JSON
        return f'{{"name":"{name}", "id":{id_}}}'


# 4. Client code works only with IReports
class Client:
    def get_report(self, report: IReports, raw_data: str):
        print("Processed JSON:", report.get_json_data(raw_data))


if __name__ == "__main__":
    # 1. Create the adaptee
    xml_provider = XmlDataProvider()

    # 2. Make our adapter
    adapter = XmlDataProviderAdapter(xml_provider)

    # 3. Give it some raw data
    raw_data = "Alice:42"

    # 4. Client prints the JSON
    client = Client()
    client.get_report(adapter, raw_data)
    # → Processed JSON: {"name":"Alice", "id":42}

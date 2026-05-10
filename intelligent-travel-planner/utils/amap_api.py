"""高德地图API工具模块"""

import hashlib
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from config.settings import settings


@dataclass
class AMapConfig:
    """高德API配置"""
    api_key: str = "7d516a18e74a0e0418ef7bcb48b52e74"
    security_key: str = ""
    base_url: str = "https://restapi.amap.com/v3"


class AMapAPI:
    """高德地图API封装"""

    def __init__(self, config: AMapConfig = None):
        self.config = config or AMapConfig()

    def _sign_request(self, params: dict) -> str:
        """生成数字签名（如果需要）"""
        # Web端API通常只需要key，签名用于服务端
        return params

    def _request(self, endpoint: str, params: dict) -> dict:
        """发送API请求"""
        params["key"] = self.config.api_key
        url = f"{self.config.base_url}/{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"高德API请求失败: {e}")
            return {"status": "0", "info": str(e)}

    def search_pois(
        self,
        keywords: str,
        city: str = None,
        citylimit: bool = True,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜索POI（兴趣点）

        Args:
            keywords: 搜索关键词
            city: 城市名称或adcode
            citylimit: 是否限制在城市范围内
            page_size: 每页结果数

        Returns:
            POI列表
        """
        params = {
            "keywords": keywords,
            "city": city or "",
            "citylimit": "true" if citylimit else "false",
            "offset": page_size,
            "extensions": "all",
        }

        result = self._request("place/text", params)

        if result.get("status") == "1" and "pois" in result:
            return result["pois"]
        return []

    def search_scenic_spots(
        self,
        city: str,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜索城市景点

        Args:
            city: 城市名称
            page_size: 结果数量

        Returns:
            景点列表
        """
        keywords = "风景名胜|旅游景点|公园|博物馆|古迹"
        return self.search_pois(keywords, city, citylimit=True, page_size=page_size)

    def search_hotels(
        self,
        city: str,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜索酒店

        Args:
            city: 城市名称
            page_size: 结果数量

        Returns:
            酒店列表
        """
        keywords = "酒店|宾馆|民宿|旅馆"
        return self.search_pois(keywords, city, citylimit=True, page_size=page_size)

    def search_restaurants(
        self,
        city: str,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜索餐厅

        Args:
            city: 城市名称
            page_size: 结果数量

        Returns:
            餐厅列表
        """
        keywords = "餐厅|饭店|美食|小吃"
        return self.search_pois(keywords, city, citylimit=True, page_size=page_size)

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI的ID

        Returns:
            POI详细信息
        """
        params = {"id": poi_id}
        result = self._request("place/detail", params)

        if result.get("status") == "1" and "pois" in result and result["pois"]:
            return result["pois"][0]
        return {}

    def geocode(self, address: str, city: str = None) -> Dict[str, Any]:
        """
        地址转经纬度

        Args:
            address: 地址
            city: 城市

        Returns:
            包含经纬度的字典
        """
        params = {"address": address}
        if city:
            params["city"] = city

        result = self._request("geocode/geo", params)

        if result.get("status") == "1" and "geocodes" in result and result["geocodes"]:
            geo = result["geocodes"][0]
            return {
                "location": geo.get("location", ""),
                "lng": geo.get("location", "").split(",")[0] if geo.get("location") else "",
                "lat": geo.get("location", "").split(",")[1] if geo.get("location") else "",
                "level": geo.get("level", ""),
                "adcode": geo.get("adcode", ""),
            }
        return {}

    def get_driving_route(
        self,
        origin: str,
        destination: str,
    ) -> Dict[str, Any]:
        """
        获取驾车路线规划

        Args:
            origin: 起点经纬度 "lng,lat"
            destination: 终点经纬度 "lng,lat"

        Returns:
            路线信息
        """
        params = {
            "origin": origin,
            "destination": destination,
            "extensions": "all",
        }

        result = self._request("direction/driving", params)

        if result.get("status") == "1" and "route" in result:
            route = result["route"]
            paths = route.get("paths", [])
            if paths:
                path = paths[0]  # 最优路线
                return {
                    "distance": int(path.get("distance", 0)),
                    "duration": int(path.get("duration", 0)),
                    "tolls": float(path.get("tolls", 0)),
                    "steps": len(path.get("steps", [])),
                }
        return {}

    def get_weather(self, city: str) -> Dict[str, Any]:
        """
        获取城市天气

        Args:
            city: 城市adcode或名称

        Returns:
            天气信息
        """
        params = {"city": city, "extensions": "base"}
        result = self._request("weather/weatherInfo", params)

        if result.get("status") == "1" and "lives" in result and result["lives"]:
            live = result["lives"][0]
            return {
                "city": live.get("city", ""),
                "weather": live.get("weather", ""),
                "temperature": live.get("temperature", ""),
                "wind_direction": live.get("winddirection", ""),
                "wind_power": live.get("windpower", ""),
                "humidity": live.get("humidity", ""),
            }
        return {}

    def get_city_info(self, city_name: str) -> Dict[str, Any]:
        """
        获取城市信息

        Args:
            city_name: 城市名称

        Returns:
            城市信息（adcode等）
        """
        params = {"keywords": city_name, "subdistrict": 0}
        result = self._request("config/district", params)

        if result.get("status") == "1" and "districts" in result and result["districts"]:
            district = result["districts"][0]
            return {
                "adcode": district.get("adcode", ""),
                "name": district.get("name", ""),
                "center": district.get("center", ""),
                "level": district.get("level", ""),
            }
        return {}


# 全局实例
amap_api = AMapAPI()

from silvertine.adapter.ibrokers.ibrokers import IBAdapter
from silvertine.core.engine import EventEngine
from silvertine.server.engine import MainEngine


def main() -> None:
    """主入口函数"""

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine=event_engine)
    main_engine.add_adapter(IBAdapter)



if __name__ == "__main__":
    main()



from org.slf4j import LoggerFactory



net_price=ir.getItem("currentnet").state
LoggerFactory.getLogger("org.openhab.core.automation.examples").info("Awattar Preis netto: {}", net_price)
# include 3% exchange fee. 1.5 ct Awattar fee + 0.78 net cost + 0.1 ct net loss cost
grossprice=(net_price.floatValue()*1.03+1.5+5.77+0.78+0.1)*1.2

LoggerFactory.getLogger("org.openhab.core.automation.examples").info("Awattar Preis gesamt: {}", grossprice)

events.postUpdate(ir.getItem("totalprice"),grossprice)
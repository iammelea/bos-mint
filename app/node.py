from peerplays import PeerPlays
from peerplays.account import Account
from peerplays.sport import Sport, Sports
from . import config
from functools import wraps
from peerplays.eventgroup import EventGroups, EventGroup
from peerplays.event import Events, Event
from peerplays.bettingmarketgroup import BettingMarketGroup, BettingMarketGroups
from peerplays.bettingmarket import BettingMarkets, BettingMarket
from peerplays.rule import Rules, Rule
from peerplays.proposal import Proposals
from app import wrapper
from peerplaysbase.objects import EventStatus, BettingMarketGroupStatus


class NodeException(Exception):
    pass


class NonScalableRequest(NodeException):
    def __init__(self):
        NodeException.__init__(
            self,
            'This request would mean to select all objects of this type, please select a parent'
        )


class BroadcastActiveOperationsExceptions(NodeException):
    def __init__(self):
        NodeException.__init__(self, 'Broadcast or cancel the pending operations first')


class ApiServerDown(NodeException):
    pass


def proposedOperation(func):
    @wraps(func)
    def wrapper(self, *arg, **kw):
        from app import utils

        self.ensureProposal()
        res = func(self, *arg, **kw)
        # investigate this
        res.__repr__()
        # the operation in the transaction must be a
        # proposal
        if utils.isProposal(res):
            # extract relative identifier
            operations = utils.getProposalOperations(res)
            # last is last added
            return operations[len(operations) - 1]
        else:
            # should never happen
            raise NodeException("Received transaction is not a proposal")
        return res

    return wrapper


class Node(object):
    #: The static connection
    node = None
    pendingProposal = None

    def __init__(self, url=None, num_retries=1, **kwargs):
        """ This class is a singelton and makes sure that only one
            connection to the node is established and shared among
            flask threads.
        """
        if not url:
            use = config["connection"]["use"]
            self.connection_config = config["connection"][use]
            self.url = config.get("connection", None)
        else:
            self.url = url
        self.num_retries = num_retries
        self.kwargs = kwargs
        self.kwargs["num_retries"] = num_retries

    def get_node(self):
        if not Node.node:
            self.connect()
        return Node.node

    def connect(self):
        try:
            Node.node = PeerPlays(
                **self.connection_config
            )
            set_shared_peerplays_instance(Node.node)
        except Exception:
            raise ApiServerDown

    def getAccount(self, name):
        try:
            return Account(name, peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def validateAccount(self, privateKey):
        try:
            return self.get_node().wallet.getAccountFromPrivateKey(privateKey)
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def ensureProposal(self):
        # deprecated code, can be removed with next peerplays update
        if not Node.pendingProposal:
            # no active proposal, create one
            Node.pendingProposal = self.get_node().proposal(
                proposer=self.getProposerAccountName())

    def getSelectedAccount(self):
        # so far default is always active
        try:
            return Account(
                self.get_node().config["default_account"],
                peerplays_instance=self.get_node()
            )
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getAccounts(self, idList):
        accounts = []
        try:
            for accountId in idList:
                accounts.append(Account(accountId,
                                        peerplays_instance=self.get_node()))
            return accounts
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def selectAccount(self, accountId):
        # if there are any pending operations the user need to finish
        # that first
        if self.getPendingTransaction() and len(self.getPendingTransaction().list_operations()) > 0:
            raise BroadcastActiveOperationsExceptions
        try:
            account = Account(accountId, peerplays_instance=self.get_node())
            self.get_node().config["default_account"] = account['name']
            return account['id'] + ' - ' + account['name']
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getAllAccountsOfWallet(self):
        try:
            # so far default is always active
            return self.get_node().wallet.getAccounts()
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def addAccountToWallet(self, privateKey):
        try:
            # ensure public key belongs to an account
            self.validateAccount(privateKey),
            self.get_node().wallet.addPrivateKey(privateKey)

            if self.get_node().config["default_account"] is None:
                accounts = self.getAllAccountsOfWallet()
                if len(accounts):
                    self.get_node().config["default_account"] = (
                        accounts[0]["name"]
                    )
                    self.selectAccount(accounts[0]["account"]["id"])

        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getSelectedAccountName(self):
        try:
            # so far default is always active
            return self.get_node().config["default_account"]
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getAllProposals(self, accountName="witness-account"):
        try:
            return Proposals(accountName, peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getPendingProposal(self):
        try:
            # so far default is pendingProposal
            return Node.pendingProposal
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getPendingTransaction(self):
        try:
            # so far default is pendingProposal
            return Node.pendingProposal
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def getProposerAccountName(self):
        return self.getSelectedAccountName()

    def wallet_exists(self):
        return self.get_node().wallet.created()

    def wallet_create(self, pwd):
        return self.get_node().wallet.create(pwd)

    def unlock(self, pwd):
        return self.get_node().wallet.unlock(pwd)

    def lock(self):
        return self.get_node().wallet.lock()

    def locked(self):
        return self.get_node().wallet.locked()

    def getSport(self, name):
        try:
            # select sport
            sport = Sport(name, peerplays_instance=self.get_node())
            # create wrappe
            return wrapper.Sport(**dict(sport))
        except Exception as ex:
            raise NodeException(
                "Sport (id={}) could not be loaded: {}".format(name, str(ex)))

    def getEventGroup(self, sportId):
        try:
            return EventGroup(sportId, peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(
                "EventGroups could not be loaded: {}".format(str(ex)))

    def getSportAsList(self, name):
        try:
            sport = Sport(name, peerplays_instance=self.get_node())
            return [(sport["id"], sport["name"][0][1])]
        except Exception as ex:
            raise NodeException(
                "EventGroups could not be loaded: {}".format(str(ex)))

    def getEvent(self, eventId):
        try:
            return Event(eventId, peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(
                "Event could not be loaded: {}".format(str(ex)))

    def getBettingMarketGroup(self, bmgId):
        try:
            return BettingMarketGroup(bmgId,
                                      peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(
                "BettingMarketGroup could not be loaded: {}".format(str(ex)))

    def getBettingMarket(self, bmId):
        try:
            return BettingMarket(bmId, peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(
                "BettingMarkets could not be loaded: {}".format(str(ex)))

    def getBettingMarketGroupRule(self, bmgrId):
        try:
            return Rule(bmgrId, peerplays_instance=self.get_node())
        except Exception as ex:
            raise NodeException(
                "BettingMarkets could not be loaded: {}".format(str(ex)))

    def getSports(self):
        try:
            return Sports(peerplays_instance=self.get_node()).sports
        except Exception as ex:
            raise NodeException("Sports could not be loaded: {}".format(str(ex)))

    def getSportsAsList(self):
        try:
            sports = Sports(peerplays_instance=self.get_node()).sports
            return [(x["id"], x["name"][0][1]) for x in sports]
        except Exception as ex:
            raise NodeException("Sports could not be loaded: {}".format(str(ex)))

    def getEventGroups(self, sportId):
        if not sportId:
            raise NonScalableRequest
        try:
            return EventGroups(sportId,
                               peerplays_instance=self.get_node()).eventgroups
        except Exception as ex:
            raise NodeException(
                "EventGroups could not be loaded: {}".format(str(ex)))

    def getEvents(self, eventGroupId):
        if not eventGroupId:
            raise NonScalableRequest
        try:
            return Events(eventGroupId,
                          peerplays_instance=self.get_node()).events
        except Exception as ex:
            raise NodeException(
                "Events could not be loaded: {}".format(str(ex)))

    def getBettingMarketGroupRules(self):
        try:
            return Rules(peerplays_instance=self.get_node()).rules
        except Exception as ex:
            raise NodeException(
                "BettingMarketGroupRules could not be loaded:{}".format(str(ex)))

    def getBettingMarketGroups(self, eventId):
        if not eventId:
            raise NonScalableRequest
        try:
            return BettingMarketGroups(
                eventId,
                peerplays_instance=self.get_node()).bettingmarketgroups
        except Exception as ex:
            raise NodeException(
                "BettingMarketGroup could not be loaded: {}".format(str(ex)))

    def getBettingMarkets(self, bettingMarketGroupId):
        if not bettingMarketGroupId:
            raise NonScalableRequest
        try:
            return BettingMarkets(
                bettingMarketGroupId,
                peerplays_instance=self.get_node()).bettingmarkets
        except Exception as ex:
            raise NodeException(
                "BettingMarkets could not be loaded: {}".format(str(ex)))

    @proposedOperation
    def createSport(self, istrings):
        try:
            return self.get_node().sport_create(
                istrings,
                account=self.getSelectedAccountName(),
                append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def createEventGroup(self, istrings, sportId):
        try:
            return self.get_node().event_group_create(istrings, sportId, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def createEvent(self, name, season, startTime, eventGroupId, status=None):
        try:
            return self.get_node().event_create(name, season, startTime, eventGroupId, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def createBettingMarketGroup(self, description, eventId, bettingMarketRuleId, asset):
        try:
            return self.get_node().betting_market_group_create(description, eventId, bettingMarketRuleId, asset, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def createBettingMarket(self, payoutCondition, description, bettingMarketGroupId):
        try:
            return self.get_node().betting_market_create(payoutCondition, description, bettingMarketGroupId, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def createBettingMarketGroupRule(self, name, description):
        try:
            return self.get_node().betting_market_rules_create(name, description, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def updateSport(self, sportId, istrings):
        try:
            return self.get_node().sport_update(sportId, istrings, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def updateEventGroup(self, eventGroupId, istrings, sportId):
        try:
            return self.get_node().event_group_update(eventGroupId, istrings, sportId, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def updateEvent(self, eventId, name, season, startTime, eventGroupId, status):
        try:
            return self.get_node().event_update(eventId, name, season, startTime, eventGroupId, status, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def updateBettingMarketGroup(self, bmgId, description, eventId, rulesId, status):
        try:
            return self.get_node().betting_market_group_update(bmgId, description, eventId, rulesId, status, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def updateBettingMarketGroupRule(self, bmgrId, name, description):
        try:
            return self.get_node().betting_market_rules_update(bmgrId, name, description, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def updateBettingMarket(self, bmId, payout_condition, descriptions, bmgId):
        try:
            return self.get_node().betting_market_update(bmId, payout_condition, descriptions, bmgId, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def startEvent(self, eventId):
        try:
            return self.get_node().event_update_status(eventId, "in_progress", None, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def finishEvent(self, eventId, scores):
        try:
            return self.get_node().event_update_status(eventId, "finished", scores, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def freezeEvent(self, eventId, scores):
        try:
            return self.get_node().event_update_status(eventId, "frozen", scores, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def cancelEvent(self, eventId, scores):
        try:
            return self.get_node().event_update_status(eventId, "canceled", scores, self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def freezeBettingMarketGroup(self, bmgId):
        try:
            return self.get_node().betting_market_group_update(bmgId, status="frozen", account=self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def unfreezeBettingMarketGroup(self, bmgId):
        try:
            return self.get_node().betting_market_group_update(bmgId, status="in_play", account=self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    @proposedOperation
    def cancelBettingMarketGroup(self, bmgId):
        try:
            return self.get_node().betting_market_group_update(bmgId, status="canceled", account=self.getSelectedAccountName(), append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def discardPendingTransaction(self):
        try:
            if Node.pendingProposal:
                self.get_node().clear()
                Node.pendingProposal = []
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def broadcastPendingTransaction(self):
        try:
            if Node.pendingProposal:
                returnV = self.get_node().broadcast()
                self.get_node().clear()
                Node.pendingProposal = []
                return returnV
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def acceptProposal(self, proposalId):
        try:
            return self.get_node().approveproposal(
                [proposalId],
                self.getSelectedAccountName(),
                self.getSelectedAccountName())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def rejectProposal(self, proposalId):
        try:
            return self.get_node().disapproveproposal(
                [proposalId],
                self.getSelectedAccountName(),
                self.getSelectedAccountName())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

    def resolveBettingMarketGroup(self, bettingMarketGroupId, resultList):
        try:
            return self.get_node().betting_market_resolve(
                bettingMarketGroupId,
                resultList,
                self.getSelectedAccountName(),
                append_to=self.getPendingProposal())
        except Exception as ex:
            raise NodeException(ex.__class__.__name__ + ": " + str(ex))

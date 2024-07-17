# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service
from ncs.dp import Action
import time


# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbacks(Service):

    # The create() callback is invoked inside NCS FASTMAP and
    # must always exist.
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info('Service create(service=', service._path, ')')

        vars = ncs.template.Variables()
        vars.add('DUMMY', '127.0.0.1')
        template = ncs.template.Template(service)
        template.apply('nanotest-template', vars)

    # The pre_modification() and post_modification() callbacks are optional,
    # and are invoked outside FASTMAP. pre_modification() is invoked before
    # create, update, or delete of the service, as indicated by the enum
    # ncs_service_operation op parameter. Conversely
    # post_modification() is invoked after create, update, or delete
    # of the service. These functions can be useful e.g. for
    # allocations that should be stored and existing also when the
    # service instance is removed.

    # @Service.pre_modification
    # def cb_pre_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')

    # @Service.post_modification
    # def cb_post_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service postmod(service=', kp, ')')


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')

        # Service callbacks require a registration for a 'service point',
        # as specified in the corresponding data model.
        #
        self.register_service('nanotest-servicepoint', ServiceCallbacks)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.
        self.register_action('checkBGP-point', CheckBGPAction)
        self.register_action('pingLoopback-point', pingLoopbackAction)

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')

class CheckBGPAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        self.log.info('checkBGP Action called (service=)', kp, ')')
        with ncs.maapi.single_read_trans(uinfo.username, uinfo.context) as trans:
            # get root path
            root = ncs.maagic.get_root(trans, kp)
            service = ncs.maagic.cd(root, kp)

            # get addresses
            dev1 = service.dev1
            dev2 = service.dev2
            
            dev1loop = root.ncs__devices.device[dev1].config.cisco_ios_xr__interface.Loopback['0'].ipv4.address.ip
            dev2loop = root.ncs__devices.device[dev2].config.cisco_ios_xr__interface.Loopback['0'].ipv4.address.ip

            #self.log.info("dev1loop = ",dev1loop)
            #self.log.info("dev2loop = ",dev2loop)

            count = 0
            while count < 5:
            # check BGP status
                if self.check_bgp(trans, dev1, dev2loop):
                    msg = "BGP session to "+dev2loop+" is Established!"
                    break
                else:
                    msg = "BGP session to "+dev2loop+" is down..."
                    count += 1
                    time.sleep(5)
            output.dev1 = msg

            count = 0
            while count < 5:
                if self.check_bgp(trans, dev2, dev1loop):
                    msg = "BGP session to "+dev1loop+" is Established!"
                    break
                else:
                    msg = "BGP session to "+dev1loop+" is down..."
                    count += 1
                    time.sleep(5)
            output.dev2 = msg

    def check_bgp(self, trans, dev_name, bgp_nbr_addr):
        root = ncs.maagic.get_root(trans)
        device = root.ncs__devices.device[dev_name]
        ret = False
        try:
            command = "show bgp neighbor brief"
            #self.log.info('command: ', command)
            live_input = device.live_status.cisco_ios_xr_stats__exec.any.get_input()
            live_input.args = [command]
            output = device.live_status.cisco_ios_xr_stats__exec.any(live_input)
            #self.log.info("bgp_status output: ", output)
            #self.log.info("bgp_nbr_addr: ", bgp_nbr_addr)

            # parse output
            for line in output.result.split("\n"):
                if len(line)>0:
                    # if line start with the number, the line is neighbor info
                    words = line.split(" ")
                    #self.log.info(words)
                    #self.log.info("words[0]: ", words[0])
                    if bgp_nbr_addr in words[0] and "Established" in words[-2]:
                        ret = True
                        self.log.info("BGP session to ", bgp_nbr_addr, "is Established!")

            if ret == False:
                self.log.info("BGP session to ", bgp_nbr_addr, "is down...")

        except Exception as e:
            self.log.info(dev_name, " command error: ", str(e))

        return ret
    

class pingLoopbackAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        self.log.info('PING Action called (service=)', kp, ')')
        with ncs.maapi.single_read_trans(uinfo.username, uinfo.context) as trans:
            # get root path
            root = ncs.maagic.get_root(trans, kp)
            service = ncs.maagic.cd(root, kp)

            # get addresses
            dev1 = service.dev1
            dev2 = service.dev2
            
            dev1loop = root.ncs__devices.device[dev1].config.cisco_ios_xr__interface.Loopback['0'].ipv4.address.ip
            dev2loop = root.ncs__devices.device[dev2].config.cisco_ios_xr__interface.Loopback['0'].ipv4.address.ip

            #self.log.info("dev1loop = ",dev1loop)
            #self.log.info("dev2loop = ",dev2loop)

            output.result = False
            count = 0

            # execute Ping
            if self.ping_Loopback(trans, dev1, dev2loop):
                msg = "Ping to "+dev2loop+" succeeded!"
                count += 1
            else:
                msg = "Ping to "+dev2loop+" failed!"
            output.dev1 = msg

            if self.ping_Loopback(trans, dev2, dev1loop):
                msg = "Ping to "+dev1loop+" succeeded!"
                count += 1
            else:
                msg = "Ping to "+dev1loop+" failed!"
            output.dev2 = msg

            if count == 2:
                output.result = True

        if output.result:
            #self.log.info("output.result == True")
            with ncs.maapi.single_write_trans(uinfo.username, uinfo.context) as trans:
                # get root path
                root = ncs.maagic.get_root(trans, kp)
                service = ncs.maagic.cd(root, kp)

                #self.log.info(service.if_configured)
                # trigger next stage
                service.if_configured = True
                #self.log.info(service.if_configured)
                trans.apply()

    def ping_Loopback(self, trans, dev_name, loopaddr):
        root = ncs.maagic.get_root(trans)
        device = root.ncs__devices.device[dev_name]
        ret = False
        try:
            command = "ping "+loopaddr
            #self.log.info('command: ', command)
            live_input = device.live_status.cisco_ios_xr_stats__exec.any.get_input()
            live_input.args = [command]
            output = device.live_status.cisco_ios_xr_stats__exec.any(live_input)
            #self.log.info("bgp_status output: ", output)
            #self.log.info("loopaddr: ", loopaddr)

            # parse output
            for line in output.result.split("\n"):
                #self.log.info(line)
                if len(line)>0:
                    # if line start with the number, the line is neighbor info
                    if "!!" in line:
                        ret = True
                        self.log.info("ping from ", dev_name, " to ", loopaddr, " succeeded!")

        except Exception as e:
            self.log.info(dev_name, " command error: ", str(e))

        return ret
            





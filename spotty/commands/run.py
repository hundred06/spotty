from argparse import ArgumentParser, Namespace
import re
import pystache
from spotty.commands.abstract_config_command import AbstractConfigCommand
from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter
from spotty.errors.instance_not_running import InstanceNotRunningError
from spotty.helpers.ssh import run_script
from spotty.providers.abstract_instance_manager import AbstractInstanceManager


class RunCommand(AbstractConfigCommand):

    name = 'run'
    description = 'Run a script from the configuration file inside the Docker container'

    def configure(self, parser: ArgumentParser):
        super().configure(parser)
        parser.add_argument('-s', '--session-name', type=str, default=None, help='tmux session name')
        parser.add_argument('-S', '--sync', action='store_true', help='Sync the project before running the script')
        parser.add_argument('-l', '--logging', action='store_true', help='Log the script outputs to the file')
        parser.add_argument('-r', '--restart', action='store_true',
                            help='Restart the script (kills previous session if it exists)')
        parser.add_argument('script_name', metavar='SCRIPT_NAME', type=str, help='Script name')
        parser.add_argument('-p', '--parameters', metavar='PARAMETER=VALUE', nargs='*', type=str, default=[],
                            help='Script parameters')

    def _run(self, instance_manager: AbstractInstanceManager, args: Namespace, output: AbstractOutputWriter):
        script_name = args.script_name
        script_params = args.parameters
        logging = args.logging

        # check that the script exists
        scripts = instance_manager.project_config.scripts
        if script_name not in scripts:
            raise ValueError('Script "%s" is not defined in the configuration file.' % script_name)

        # get script parameters
        params = {}
        for param in script_params:
            match = re.match('(\w+)=(.*)', param)
            if not match:
                raise ValueError('Invalid script parameter: "%s"' % param)

            param_name, param_value = match.groups()
            if param_name in params:
                raise ValueError('Parameter "%s" defined twice' % param_name)

            params[param_name] = param_value

        # check that the instance is started
        if not instance_manager.is_running():
            raise InstanceNotRunningError(instance_manager.instance_config.name)

        # sync the project with the instance
        if args.sync:
            instance_manager.sync(output)

        # tmux session name
        session_name = args.session_name if args.session_name else 'spotty-script-%s' % script_name

        # replace script parameters
        script_content = pystache.render(scripts[script_name], params)

        # run the script on the instance
        run_script(host=instance_manager.ip_address,
                   user=instance_manager.ssh_user,
                   key_path=instance_manager.ssh_key_path,
                   script_name=script_name,
                   script_content=script_content,
                   tmux_session_name=session_name,
                   restart=args.restart,
                   logging=logging,
                   local_ssh_port=instance_manager.instance_config.local_ssh_port)

import json
import logging
import logging.config
import os
CURRENT_DIR =os.path.dirname(os.path.abspath(__file__))


def setup_logging():
    """
    This script loads the configs of the logger and should be called ones when running the code to get log messages
    """
    #load config file
    with open(os.path.join(CURRENT_DIR, '..', '..', 'data/config/logging_conf.json'), 'r') as config_file:
        logging_config = json.load(config_file)
   
    #update the filename for the logs
    for handler in logging_config['handlers'].values():
        if 'filename' in handler:
            handler['filename'] = os.path.abspath(
                os.path.join(CURRENT_DIR, '..', '..', handler['filename'])
            )

    # Apply the logging configuration
    logging.config.dictConfig(logging_config)
    
    #now the logger can be used
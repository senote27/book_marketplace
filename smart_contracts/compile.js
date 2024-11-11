const fs = require('fs');
const path = require('path');
const solc = require('solc');

// Ensure build directory exists
const buildPath = path.resolve(__dirname, 'build', 'contracts');
if (!fs.existsSync(buildPath)) {
    fs.mkdirSync(buildPath, { recursive: true });
}

function compileContract(contractName) {
    // Read the Solidity contract source code
    const contractPath = path.resolve(__dirname, `${contractName}.sol`);
    const source = fs.readFileSync(contractPath, 'utf8');

    // Prepare compiler input
    const input = {
        language: 'Solidity',
        sources: {
            [contractName]: {
                content: source,
            },
        },
        settings: {
            outputSelection: {
                '*': {
                    '*': ['*'],
                },
            },
            optimizer: {
                enabled: true,
                runs: 200,
            },
        },
    };

    // Compile the contract
    const output = JSON.parse(solc.compile(JSON.stringify(input)));

    // Check for errors
    if (output.errors) {
        output.errors.forEach(error => {
            console.error(error.formattedMessage);
        });
        
        // Throw if there are any errors
        if (output.errors.find(error => error.severity === 'error')) {
            throw new Error('Compilation failed');
        }
    }

    // Extract compiled contract
    const contract = output.contracts[contractName][contractName];

    // Write the bytecode and ABI to files
    const buildArtifact = {
        contractName: contractName,
        abi: contract.abi,
        bytecode: contract.evm.bytecode.object,
        deployedBytecode: contract.evm.deployedBytecode.object,
        metadata: contract.metadata,
        compiler: {
            name: 'solc',
            version: solc.version(),
        },
        networks: {},
    };

    fs.writeFileSync(
        path.resolve(buildPath, `${contractName}.json`),
        JSON.stringify(buildArtifact, null, 2)
    );

    console.log(`${contractName} contract compiled successfully!`);
    console.log(`ABI and bytecode saved to: ${path.resolve(buildPath, `${contractName}.json`)}`);

    return buildArtifact;
}

// Compile BookMarket contract
try {
    compileContract('BookMarket');
} catch (error) {
    console.error('Compilation failed:', error);
    process.exit(1);
}